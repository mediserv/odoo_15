from odoo.exceptions import UserError
from odoo import models, fields, api, _


class UpgradeDowngradeWizard(models.TransientModel):
    _name = 'upgrade.downgrade'
    _description = 'Upgrade \ Downgrade'
    
    def _default_subscription(self):
        return self.env['sale.subscription'].browse(self._context.get('active_id'))

    subscription_id = fields.Many2one('sale.subscription', string="Subscription", required=True,
                                      default=_default_subscription, ondelete="cascade")
    
    def _default_products(self):
        self = self.with_context(active_test=False)
        subscription_id = self.env['sale.subscription'].browse(self._context.get('active_id'))
        sub_default_products = subscription_id.upgrade_product_ids
        res_ids = []
        Options = self.env['sale.subscription.upgrade.downgrade.wizard.keep_options']
        for product_id in sub_default_products:
            quantity = subscription_id.recurring_invoice_line_ids.filtered(
                lambda p: p.product_id == product_id).mapped('quantity')
            name = subscription_id.recurring_invoice_line_ids.filtered(
                lambda p: p.product_id == product_id).mapped('name')
            covered_member = subscription_id.recurring_invoice_line_ids.filtered(
                lambda p: p.product_id == product_id).mapped('covered_member')
            commencement_date = subscription_id.recurring_invoice_line_ids.filtered(
                lambda p: p.product_id == product_id).mapped('commencement_date')
            value = {'name': name[0],
                     'downgrade_plan': False,
                     'product_id': product_id.id,
                     'quantity': quantity[0],
                     'covered_member_name': covered_member.name,
                     'commencement_date': commencement_date[0]
                    }
            res_ids.append((0, 0, value))
            Options |= Options.new(value)
        return Options
    new_commencement_date = fields.Date(string = 'New Commencement Date', required=True,)
    
    sub_list_product_ids = fields.One2many('sale.subscription.upgrade.downgrade.wizard.keep_options',
                                                'wizard_id',
                                                default=_default_products, string="Archived products",
                                                help="If checked, the product will be reused in the renewal order")
    upgrade_line_ids = fields.One2many('upgrade.downgrade.wizard.upgrade_option',
                                           'wizard_id', string="Replaced by")
    
    def create_downgrade_upgrade_order(self):
        subscription = self.env['sale.subscription'].browse(self._context.get('active_id'))
        self = self.with_company(self.subscription_id.company_id)
        kept_products = self.sub_list_product_ids.filtered(lambda rec: rec.downgrade_plan is False)
        kept_product_ids = [x['product_id'] for x in kept_products]
        subscription.write({'to_upgrade': True})
        # Update the subscription lines to remove discarded products and add new products
        return self.subscription_id.prepare_upgrade_downgrade_order(new_commencement_date=self.new_commencement_date, kept_products=kept_product_ids, new_lines_ids=self.upgrade_line_ids, )


                
    
class UpgradeDowngradeWizardKeepOption(models.TransientModel):
    _name = "sale.subscription.upgrade.downgrade.wizard.keep_options"
    _description = "Upgrade Downgrade Subscription Lines Wizard"

    downgrade_plan = fields.Boolean("Downgrade", default=True)
    name = fields.Char('Product')
    product_id = fields.Integer("id")
    quantity = fields.Integer()
    wizard_id = fields.Many2one('upgrade.downgrade', required=True, ondelete="cascade")
    covered_member_id = fields.Integer("covered member id")
    covered_member_name = fields.Char('Covered Members')
    commencement_date = fields.Date(string = 'Commencement Date',)



class UpgradeDowngradeWizardUpgradeOption(models.TransientModel):
    _name = "upgrade.downgrade.wizard.upgrade_option"
    _description = "Subscription Upgrade Options"

    wizard_id = fields.Many2one('upgrade.downgrade', required=True, ondelete="cascade")
    name = fields.Char(string="Description", compute='_compute_product_attributes')
    product_id = fields.Many2one('product.product', required=True, domain="[('recurring_invoice', '=', True)]",
                                 ondelete="cascade")
    uom_id = fields.Many2one('uom.uom', string="Unit of Measure", required=True, ondelete="cascade",
                             domain="[('category_id', '=', product_uom_category_id)]",
                             compute='_compute_product_attributes',
                             readonly=False)
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True)
    quantity = fields.Float(default=1.0)

    def _compute_product_attributes(self):
        for option in self:
            if option.product_id:
                option.name = option.product_id.get_product_multiline_description_sale()
                if not option.uom_id or option.product_id.uom_id.category_id.id != option.uom_id.category_id.id:
                    option.uom_id = option.product_id.uom_id.id
