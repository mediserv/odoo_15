import logging
import datetime
import traceback

from ast import literal_eval
from collections import Counter
from dateutil.relativedelta import relativedelta
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import format_date, float_compare
from odoo.tools.float_utils import float_is_zero


class SaleSubscription(models.Model):
    _inherit = "sale.subscription"
    
    to_upgrade =fields.Boolean('To Upgrade')
    to_downgrade =fields.Boolean('To Downgrade')

    
    def _coverage_start_date(self):
        for sub in self:
            next_date1 = self.recurring_next_date
            coverage_start_date = next_date1 + relativedelta(months=1)
            sub.x_coverage_startdate = coverage_start_date
    

    def _prepare_invoice_data(self):
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_("You must first select a Customer for Subscription %s!", self.name))

        company = self.env.company or self.company_id

        journal = self.template_id.journal_id or self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError(_('Please define a sale journal for the company "%s".') % (company.name or '', ))

        next_date = self.recurring_next_date
        if not next_date:
            raise UserError(_('Please define Date of Next Invoice of "%s".') % (self.display_name,))
        recurring_next_date = self._get_recurring_next_date(self.recurring_rule_type, self.recurring_interval, next_date, self.recurring_invoice_day)
        end_date = fields.Date.from_string(recurring_next_date) - relativedelta(days=1)     # remove 1 day as normal people thinks in term of inclusive ranges.
        addr = self.partner_id.address_get(['delivery', 'invoice'])
        sale_order = self.env['sale.order'].search([('order_line.subscription_id', 'in', self.ids)], order="id desc", limit=1)
        use_sale_order = sale_order and sale_order.partner_id == self.partner_id
        partner_id = sale_order.partner_invoice_id.id if use_sale_order else self.partner_invoice_id.id or addr['invoice']
        partner_shipping_id = sale_order.partner_shipping_id.id if use_sale_order else self.partner_shipping_id.id or addr['delivery']
        fpos = self.env['account.fiscal.position'].with_company(company).get_fiscal_position(self.partner_id.id, partner_shipping_id)
        narration = _("This invoice covers the following period: %s - %s") % (format_date(self.env, next_date), format_date(self.env, end_date))
        coverage_start = next_date + relativedelta(months=1)
        coverage_end = (recurring_next_date + relativedelta(months=1)) - relativedelta(days=1)
        if self.description:
            narration += '\n' + self.description
        elif self.env['ir.config_parameter'].sudo().get_param('account.use_invoice_terms') and self.company_id.invoice_terms:
            narration += '\n' + self.company_id.invoice_terms
        res = {
            'move_type': 'out_invoice',
            'partner_id': partner_id,
            'partner_shipping_id': partner_shipping_id,
            'currency_id': self.pricelist_id.currency_id.id,
            'journal_id': journal.id,
            'invoice_origin': self.code,
            'fiscal_position_id': fpos.id,
            'invoice_payment_term_id': self.payment_term_id.id,
            'invoice_user_id': self.user_id.id,
            'partner_bank_id': company.partner_id.bank_ids.filtered(lambda b: not b.company_id or b.company_id == company)[:1].id,
            'x_Coverage_StartDate': coverage_start, 
            'x_Coverage_Enddate' : coverage_end,
            'invoice_date' : next_date
        }
        if self.team_id:
            res['team_id'] = self.team_id.id
        return res
    
    upgrade_product_ids = fields.Many2many('product.product', string=' Products',
                                            compute='_compute_upgrade_lines')
    
    @api.depends('recurring_invoice_line_ids.product_id')
    def _compute_upgrade_lines(self):
        # Search which products are archived when reading the subscriptions lines
        self = self.with_context(active_test=False)
        for subscription in self:
            subscription.upgrade_product_ids = self.env['product.product'].search(
                [('id', 'in', subscription.recurring_invoice_line_ids.mapped('product_id').ids),
                 ('recurring_invoice', '=', True)],)


    def _prepare_upgrade_downgrade_order_values(self, new_commencement_date=False, kept_products=False, new_lines_ids=False,):
        res = dict()
        for subscription in self:
            subscription = subscription.with_company(subscription.company_id)
            order_lines = []
            kept_product_lines = []
            fpos = subscription.env['account.fiscal.position'].get_fiscal_position(subscription.partner_id.id)
            partner_lang = subscription.partner_id.lang
           
            if kept_products:
                # Prevent to add products discarded during the renewal
                line_ids = subscription.with_context(active_test=False).recurring_invoice_line_ids.filtered(
                    lambda l: l.product_id.id in kept_products)
            
                for line in line_ids:
                    product = line.product_id.with_context(lang=partner_lang) if partner_lang else line.product_id
                    kept_product_lines.append((0, 0, {
                        'product_id': product.id,
                        'name': line.name,
                        'subscription_id': subscription.id,
                        'product_uom': line.uom_id.id,
                        'product_uom_qty': line.quantity,
                        'price_unit': line.price_unit,
                        'discount': line.discount,
                        'covered_member': line.covered_member,
                        'commencement_date': line.commencement_date
                    }))
            if new_lines_ids:
                # Add products during the renewal (sort of upsell)
                for line in new_lines_ids:
                    order_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'subscription_id': subscription.id,
                        'product_uom': line.uom_id.id,
                        'product_uom_qty': line.quantity,
                        'price_unit': subscription.pricelist_id.with_context(uom=line.uom_id.id).get_product_price(
                                line.product_id, line.quantity, subscription.partner_id),
                            'discount': 0,
                        }))
            addr = subscription.partner_id.address_get(['delivery', 'invoice'])
            res[subscription.id] = {
                'pricelist_id': subscription.pricelist_id.id,
                'partner_id': subscription.partner_id.id,
                'partner_invoice_id': subscription.partner_invoice_id.id or addr['invoice'],
                'partner_shipping_id': subscription.partner_shipping_id.id or addr['delivery'],
                'currency_id': subscription.pricelist_id.currency_id.id,
                'order_line': order_lines,
                'kept_product_lines' : kept_product_lines,
                'analytic_account_id': subscription.analytic_account_id.id,
                'subscription_management': 'upgrade_downgrade',
                'origin': subscription.code,
                'note': subscription.description,
                'fiscal_position_id': fpos.id,
                'user_id': subscription.user_id.id,
                'payment_term_id': subscription.payment_term_id.id,
                'company_id': subscription.company_id.id,
                'x_commencement_date': new_commencement_date,
                'x_studio_payment_mode' : subscription.template_id.id
            }
        return res

    
    def prepare_upgrade_downgrade_order(self, new_commencement_date=False, kept_products=False, new_lines_ids=False,):
        self.ensure_one()
        values = self._prepare_upgrade_downgrade_order_values(new_commencement_date, kept_products, new_lines_ids)
        order = self.env['sale.order'].create(values[self.id])
        order.message_post(body=(_("This order has been created from the subscription ") + " <a href=# data-oe-model=sale.subscription data-oe-id=%d>%s</a>" % (self.id, self.display_name)))
        order.order_line._compute_tax_id()
        order.action_riskreserve()
        order.action_confirm()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": order.id,
        }

class SaleSubscriptionLine(models.Model):
    _inherit = "sale.subscription.line"
    _description = "Subscription Line"
    _check_company_auto = True            
            
            
    covered_member = fields.Many2one('res.partner', string = 'Covered Members', readonly = True)
    commencement_date = fields.Date(string = 'Commencement Date', readonly = True)