from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import parse_date
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from functools import partial
from itertools import groupby
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang, get_lang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from werkzeug.urls import url_encode
    

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    to_upgrade =fields.Boolean('To Upgrade') 
    kept_product_lines = fields.One2many('kept.sub.line','order_id', string='Kept Lines', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True, auto_join=True)  
    
    
    subscription_management = fields.Selection(string='Subscription Management', selection_add=[('upgrade_downgrade', 'Upgrade / Downgrade')],)
    
    
    
    def _prepare_subscription_data(self, template):
        """Prepare a dictionnary of values to create a subscription from a template."""
        self.ensure_one()
        date_today = fields.Date.context_today(self)
        commencement_date = self.x_commencement_date 
        recurring_invoice_day = commencement_date.day
        recurring_date_calcu_commencement = commencement_date - relativedelta(months=1)
        recurring_next_date = self.env['sale.subscription']._get_recurring_next_date(
            template.recurring_rule_type, template.recurring_interval,
            recurring_date_calcu_commencement, recurring_invoice_day
        )
        values = {
            'name': template.name,
            'template_id': template.id,
            'partner_id': self.partner_id.id,
            'partner_invoice_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'user_id': self.user_id.id,
            'team_id': self.team_id.id,
            'payment_term_id': self.payment_term_id.id,
            'date_start': fields.Date.context_today(self),
            'description': self.note or template.description,
            'pricelist_id': self.pricelist_id.id,
            'company_id': self.company_id.id,
            'analytic_account_id': self.analytic_account_id.id,
            'recurring_next_date': recurring_next_date,
            'recurring_invoice_day': recurring_invoice_day,
            'payment_token_id': self.transaction_ids.get_last_transaction().payment_token_id.id if template.payment_mode in ['validate_send_payment', 'success_payment'] else False
        }
        default_stage = self.env['sale.subscription.stage'].search([('category', '=', 'progress')], limit=1)
        if default_stage:
            values['stage_id'] = default_stage.id
        return values
    
    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        
        commencement_date1 = self.x_commencement_date
        invoicedate = self.x_commencement_date -  relativedelta(months=1)
        payment_mode = self.x_studio_payment_mode.id
        if payment_mode == 6:
            coverage_endate1 = (commencement_date1 + relativedelta(months=12)) - relativedelta(days=1)
        elif payment_mode == 3:
             coverage_endate1 = (commencement_date1 + relativedelta(months=1)) - relativedelta(days=1)
        
        self.ensure_one()
        journal = self.env['account.move'].with_context(default_move_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).') % (self.company_id.name, self.company_id.id))

        invoice_vals = {
            'ref': self.client_order_ref or '',
            'move_type': 'out_invoice',
            'narration': self.note,
            'currency_id': self.pricelist_id.currency_id.id,
            'campaign_id': self.campaign_id.id,
            'medium_id': self.medium_id.id,
            'source_id': self.source_id.id,
            'invoice_user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id.get_fiscal_position(self.partner_invoice_id.id)).id,
            'partner_bank_id': self.company_id.partner_id.bank_ids[:1].id,
            'journal_id': journal.id,  # company comes from the journal
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'payment_reference': self.reference,
            'transaction_ids': [(6, 0, self.transaction_ids.ids)],
            'invoice_line_ids': [],
            'company_id': self.company_id.id,
            'x_Coverage_StartDate' : commencement_date1,
            'x_Coverage_Enddate' : coverage_endate1,
            'invoice_date' : invoicedate,
        }
        return invoice_vals

    def action_riskreserve(self):
        for orders in self:
            orders.write({'order_line': orders.action_riskreserveee()})
    def action_riskreserveee(self):
        res =[]
        for line in self.order_line:
            riskreserve_search = line.product_id.x_related_riskreserve.product_variant_id
            riskreserve_check = line.x_riskreserve_check
            if riskreserve_search and not riskreserve_check:
                line.write({'x_riskreserve_check' : True})
                salesorder_lines = {
                    'product_id' :	riskreserve_search.id,
                    'sequence' : 30
                }
                res.append(salesorder_lines)
        return [(0, 0, vals) for vals in res]
    

    def action_reinstatementfee(self):
        for orders in self:
            payment_mode = orders.x_studio_payment_mode.id
            payment_type = orders.x_family_type
            res =[]
            if payment_mode == 3 and payment_type == 'i':
                res = [{
                    'product_id' :	56235,
                    'sequence' : 20},
                    {
                    'product_id' : 56599,
                    'sequence' : 20}]
            if payment_mode == 6 and payment_type == 'i':
                res = [{
                    'product_id' :	59312,
                    'sequence' : 20},
                    {
                    'product_id' :	56599,
                    'sequence' : 20}]
            if payment_mode == 3 and payment_type == 'f':
                res = [{
                    'product_id' :	56096,
                    'sequence' : 20},
                    {
                    'product_id' : 56458,
                    'sequence' : 20}]
            if payment_mode == 6 and payment_type == 'f':
                res = [{
                    'product_id' :	56457,
                    'sequence' : 20},
                    {
                    'product_id' :	56458,
                    'sequence' : 20}]
        
        orders.write({'order_line': [(0, 0, vals) for vals in res]})
        

        
    def update_existing_subscriptions(self):
        """
        Update subscriptions already linked to the order by updating or creating lines.

        :rtype: list(integer)
        :return: ids of modified subscriptions
        """
        res = []
        deleted_product_ids = None
        for order in self:
            subscriptions = order.order_line.mapped('subscription_id').sudo()
            if subscriptions:
                if (order.subscription_management != 'renew') and (order.subscription_management != 'upgrade_downgrade'):
                    order.subscription_management = 'upsell'
            res.append(subscriptions.ids)
            if order.subscription_management == 'upgrade_downgrade':
                order.to_upgrade = True
            else:
                if order.subscription_management == 'renew':
                    subscriptions.increment_period(renew=True)
                    subscriptions.wipe()
                    subscriptions.payment_term_id = order.payment_term_id
                    subscriptions.set_open()
                    # Some products of the subscription may be missing from the SO: they can be archived or manually removed from the SO.
                    # we delete the recurring line of these subscriptions
                    deleted_product_ids = subscriptions.mapped(
                        'recurring_invoice_line_ids.product_id') - order.order_line.mapped('product_id')
                for subscription in subscriptions:
                    subscription_lines = order.order_line.filtered(lambda l: l.subscription_id == subscription and l.product_id.recurring_invoice)
                    line_values = subscription_lines._update_subscription_line_data(subscription)
                    subscription.write({'recurring_invoice_line_ids': line_values})
        return res
            
    
    def create_invoice_update_subscription(self):
        date_today = fields.Date.context_today(self)
        commencement_date = self.x_commencement_date
        run_method_date = commencement_date - relativedelta(months=1)
        
        #if order.subscription_management == 'upgrade_downgrade' and date_today == run_method_date:
        
        res = []
        deleted_product_ids = None
        for order in self:
            subscriptions = order.order_line.mapped('subscription_id').sudo()
            if subscriptions:
                if (order.subscription_management != 'renew') and (order.subscription_management != 'upgrade_downgrade'):
                    order.subscription_management = 'upsell'
            res.append(subscriptions.ids)
                # we delete the recurring line of these subscriptions
            deleted_product_ids = subscriptions.mapped(
                    'recurring_invoice_line_ids.product_id') - order.order_line.mapped('product_id')
            if order.subscription_management == 'upgrade_downgrade':
                subscriptions.increment_period(renew=True)
                subscriptions.wipe()
                subscriptions.payment_term_id = order.payment_term_id
                subscriptions.set_open()
                # Some products of the subscription may be missing from the SO: they can be archived or manually removed from the SO.
                # we delete the recurring line of these subscriptions
                deleted_product_ids = subscriptions.mapped(
                    'recurring_invoice_line_ids.product_id') - order.order_line.mapped('product_id')
            for subscription in subscriptions:
                subscription_lines = order.order_line.filtered(lambda l: l.subscription_id == subscription and l.product_id.recurring_invoice)
                kept_subcription_lines = order.kept_product_lines.filtered(lambda l: l.subscription_id == subscription and l.product_id.recurring_invoice)
                kept_line_values = kept_subcription_lines._update_subscription_line_data(subscription)
                line_values = subscription_lines._update_subscription_line_data(subscription)
                combine_values = kept_line_values + line_values
                subscription.write({'recurring_invoice_line_ids': combine_values})
            order._create_invoices_upgrade_downgrade()
                
        return res

    def _create_invoices_upgrade_downgrade(self, grouped=False, final=False, date=None):
        """
        Create the invoice associated to the SO.
        :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                        (partner_invoice_id, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created invoices
        """
        if not self.env['account.move'].check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                return self.env['account.move']

        # 1) Create invoices.
        invoice_vals_list = []
        invoice_item_sequence = 0 # Incremental sequencing to keep the lines order on the invoice.
        for order in self:
            order = order.with_company(order.company_id)
            current_section_vals = None
            down_payments = order.env['sale.order.line']

            invoice_vals = order._prepare_invoice()
            invoiceable_lines = order._get_invoiceable_lines(final)
            kept_product_lines = order.get_kept_lines(final)

            if not any(not line.display_type for line in invoiceable_lines):
                continue

            invoice_line_vals = []
            for line in kept_product_lines:
                invoice_line_vals.append(
                    (0, 0, line._prepare_invoice_line(
                        sequence=invoice_item_sequence,
                    )),
                )
                invoice_item_sequence += 1

            for line in invoiceable_lines:
                invoice_line_vals.append(
                    (0, 0, line._prepare_invoice_line(
                        sequence=invoice_item_sequence,
                    )),
                )
                invoice_item_sequence += 1

            invoice_vals['invoice_line_ids'] += invoice_line_vals
            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise self._nothing_to_invoice_error()

        # 2) Manage 'grouped' parameter: group by (partner_id, currency_id).
        if not grouped:
            new_invoice_vals_list = []
            invoice_grouping_keys = self._get_invoice_grouping_keys()
            invoice_vals_list = sorted(invoice_vals_list, key=lambda x: [x.get(grouping_key) for grouping_key in invoice_grouping_keys])
            for grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: [x.get(grouping_key) for grouping_key in invoice_grouping_keys]):
                origins = set()
                payment_refs = set()
                refs = set()
                ref_invoice_vals = None
                for invoice_vals in invoices:
                    if not ref_invoice_vals:
                        ref_invoice_vals = invoice_vals
                    else:
                        ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                    origins.add(invoice_vals['invoice_origin'])
                    payment_refs.add(invoice_vals['payment_reference'])
                    refs.add(invoice_vals['ref'])
                ref_invoice_vals.update({
                    'ref': ', '.join(refs)[:2000],
                    'invoice_origin': ', '.join(origins),
                    'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
                })
                new_invoice_vals_list.append(ref_invoice_vals)
            invoice_vals_list = new_invoice_vals_list

        # 3) Create invoices.

        # As part of the invoice creation, we make sure the sequence of multiple SO do not interfere
        # in a single invoice. Example:
        # SO 1:
        # - Section A (sequence: 10)
        # - Product A (sequence: 11)
        # SO 2:
        # - Section B (sequence: 10)
        # - Product B (sequence: 11)
        #
        # If SO 1 & 2 are grouped in the same invoice, the result will be:
        # - Section A (sequence: 10)
        # - Section B (sequence: 10)
        # - Product A (sequence: 11)
        # - Product B (sequence: 11)
        #
        # Resequencing should be safe, however we resequence only if there are less invoices than
        # orders, meaning a grouping might have been done. This could also mean that only a part
        # of the selected SO are invoiceable, but resequencing in this case shouldn't be an issue.
        if len(invoice_vals_list) < len(self):
            SaleOrderLine = self.env['sale.order.line']
            for invoice in invoice_vals_list:
                sequence = 1
                for line in invoice['invoice_line_ids']:
                    line[2]['sequence'] = SaleOrderLine._get_invoice_line_sequence(new=sequence, old=line[2]['sequence'])
                    sequence += 1

        # Manage the creation of invoices in sudo because a salesperson must be able to generate an invoice from a
        # sale order without "billing" access rights. However, he should not be able to create an invoice from scratch.
        moves = self.env['account.move'].sudo().with_context(default_move_type='out_invoice').create(invoice_vals_list)
        moves.sudo().action_post()

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        if final:
            moves.sudo().filtered(lambda m: m.amount_total < 0).action_switch_invoice_into_refund_credit_note()
        for move in moves:
            move.message_post_with_view('mail.message_origin_link',
                values={'self': move, 'origin': move.line_ids.mapped('sale_line_ids.order_id')},
                subtype_id=self.env.ref('mail.mt_note').id
            )
        return moves
    
    def get_kept_lines(self, final=False):
        kept_line_ids = []
        for line in self.kept_product_lines:
            kept_line_ids.append(line.id)

        return self.env['kept.sub.line'].browse(kept_line_ids)
        
        

    
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    
    
    def _prepare_invoice_line(self, **optional_values):
        """
        Override to add subscription-specific behaviours.

        Display the invoicing period in the invoice line description, link the invoice line to the
        correct subscription and to the subscription's analytic account if present, add revenue dates.
        """
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)  # <-- ensure_one()
        if self.subscription_id:
            res.update(subscription_id=self.subscription_id.id)
            periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
            next_date = self.subscription_id.recurring_next_date or fields.Date.context_today(self)
            previous_date = next_date - relativedelta(**{periods[self.subscription_id.recurring_rule_type]: self.subscription_id.recurring_interval})
            is_already_period_msg = False
            if self.order_id.subscription_management != 'upsell':  # renewal or creation: one entire period
                date_start = previous_date
                date_start_display = previous_date
                date_end = next_date - relativedelta(days=1)  # the period does not include the next renewal date
            else:  # upsell: pro-rated period
                date_start, date_start_display, date_end = None, None, None
                try:
                    regexp = r"\[(\d{4}-\d{2}-\d{2}) -> (\d{4}-\d{2}-\d{2})\]"
                    match = re.search(regexp, self.name)
                    date_start = fields.Date.from_string(match.group(1))
                    date_start_display = date_start
                    date_end = fields.Date.from_string(match.group(2))
                except Exception:
                    _logger.error('_prepare_invoice_line: unable to compute invoicing period for %r - "%s"', self, self.name)
                    # Fallback on discount
                if not date_start or not date_start_display or not date_end:
                    # here we have a slight problem: the date used to compute the pro-rated discount
                    # (that is, the date_from in the upsell wizard) is not stored on the line,
                    # preventing an exact computation of start and end revenue dates
                    # witness me as I try to retroengineer the ~correct dates 🙆‍
                    # (based on `partial_recurring_invoice_ratio` from the sale.subscription model)
                    total_days = (next_date - previous_date).days
                    days = round((1 - self.discount / 100.0) * total_days)
                    date_start = next_date - relativedelta(days=days+1)
                    date_start_display = next_date - relativedelta(days=days)
                    date_end = next_date - relativedelta(days=1)
                else:
                    is_already_period_msg = True
            if not is_already_period_msg:
                lang = self.order_id.partner_invoice_id.lang
                format_date = self.env['ir.qweb.field.date'].with_context(lang=lang).value_to_html
                # Ugly workaround to display the description in the correct language
                if lang:
                    self = self.with_context(lang=lang)
                period_msg = _("Invoicing period") + ": [%s -> %s]" % (fields.Date.to_string(date_start_display), fields.Date.to_string(date_end))
                res.update({
                    'name': self.name
                })
            res.update({
                'subscription_start_date': date_start,
                'subscription_end_date': date_end,
            })
            if self.subscription_id.analytic_account_id:
                res['analytic_account_id'] = self.subscription_id.analytic_account_id.id
        return res
    
    
    
    def _prepare_subscription_line_data(self):
        """Prepare a dictionnary of values to add lines to a subscription."""
        values = list()
        for line in self:
            values.append((0, False, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.product_uom_qty,
                'uom_id': line.product_uom.id,
                'price_unit': line.price_unit,
                'discount': line.discount if line.order_id.subscription_management != 'upsell' else False,
                'covered_member': line.x_covered_member.id,
                'commencement_date': line.x_commencement_date,
            }))
        return values
    
    
class KeptSubLine(models.Model):
    _name = "kept.sub.line"
    _description = "Lines Kept from subcription"
    _order = 'order_id, sequence, id'
    _check_company_auto = True
    
    
    subscription_id = fields.Many2one('sale.subscription', 'Subscription', copy=False, check_company=True)
    order_id = fields.Many2one('sale.order', string='Order Reference', required=True, ondelete='cascade', index=True, copy=False)
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string="Description")
    product_id = fields.Many2one('product.product', required=True, domain="[('recurring_invoice', '=', True)]",
                                 ondelete="cascade")
    product_uom_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', required=True, default=1.0)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True)
    quantity = fields.Float(default=1.0)
    discount = fields.Float(string='Discount (%)', digits='Discount', default=0.0)
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)
    covered_member = fields.Many2one('res.partner', string = 'Covered Members', readonly = True)
    commencement_date = fields.Date(string = 'Commencement Date', readonly = True)
    company_id = fields.Many2one(related='order_id.company_id', string='Company', store=True, readonly=True, index=True)
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure", required=True, ondelete="cascade",
                             domain="[('category_id', '=', product_uom_category_id)]",
                             compute='_compute_product_attributes',
                             readonly=False)

    def _compute_product_attributes(self):
        for option in self:
            if option.product_id:
                option.name = option.product_id.get_product_multiline_description_sale()
                if not option.uom_id or option.product_id.uom_id.category_id.id != option.uom_id.category_id.id:
                    option.uom_id = option.product_id.uom_id.id


                    
    def _prepare_subscription_line_data(self):
        """Prepare a dictionnary of values to add lines to a subscription."""
        values = list()
        for line in self:
            values.append((0, False, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.product_uom_qty,
                'uom_id': line.product_uom.id,
                'price_unit': line.price_unit,
                'discount': line.discount if line.order_id.subscription_management != 'upsell' else False,
            }))
        return values

    def _update_subscription_line_data(self, subscription):
        """Prepare a dictionnary of values to add or update lines on a subscription."""
        values = list()
        dict_changes = dict()
        for line in self:
            sub_line = subscription.recurring_invoice_line_ids.filtered(
                lambda l: (l.product_id, l.uom_id, l.price_unit) == (line.product_id, line.product_uom, line.price_unit)
            )
            if sub_line:
                
                dict_changes.setdefault(sub_line.id, sub_line.quantity)
                    # upsell, we add the product to the existing quantity
                dict_changes[sub_line.id] += line.product_uom_qty
            else:
                # we create a new line in the subscription: (0, 0, values)
                values.append(line._prepare_subscription_line_data()[0])

        values += [(1, sub_id, {'quantity': dict_changes[sub_id]}) for sub_id in dict_changes]
        return values
    def _prepare_invoice_line(self, **optional_values):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        :param optional_values: any parameter that should be added to the returned invoice line
        """
        self.ensure_one()
        res = {
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.product_uom_qty,
            'discount': self.discount,
            'price_unit': self.price_unit,
            'tax_ids': [(6, 0, self.product_id.taxes_id.ids)],
            'analytic_account_id': self.order_id.analytic_account_id.id,
            'sale_line_ids': [(4, self.id)],
        }
        if optional_values:
            res.update(optional_values)
        return res
