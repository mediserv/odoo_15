from odoo.exceptions import UserError
from odoo import models, fields, api, _


class DueSaleWizard(models.TransientModel):
    _name = 'auxillary.package'
    _description = 'Auxillary package'
    
    def _default_sale(self):
        
        return self.env['sale.order'].browse(self._context.get('active_id'))

    sale_id = fields.Many2one('sale.order', string="sale", required=True, default=_default_sale, ondelete="cascade")

    currency_id = fields.Many2one("res.currency", related="sale_id.currency_id", string="Currency", required=True)
    consolatory_value_recurring = fields.Monetary('(Recurring) Consolatory Value')
    orderval_afterconsol_recurring = fields.Monetary('(Recurring) Sales Order Value after Consolatroy Benefit is Applied')
    lboctd_value_recurring = fields.Monetary('LBOCTD Pervious Plan Value (Recurring)')
    lboctd_rr_waiver = fields.Boolean(string ='Risk Reserve Waiver')
    rr_waiver_ammount = fields.Monetary('Risk Reserve Waiver Amount (Leave bank if waiver is full ammount')
    onboarding_package = fields.Boolean(string = 'Onboarding package')
    registration_package = fields.Boolean(string ='Registration Package')
    
    
    def proceed(self):
        rr_waiver_ammount = self.rr_waiver_ammount
        lboctd_rr_waiver =self.lboctd_rr_waiver
        onboarding_package = self.onboarding_package
        registration_package = self.registration_package
        consolatory_value_recurring = self.consolatory_value_recurring
        orderval_afterconsol_recurring = self.orderval_afterconsol_recurring
        lboctd_value_recurring = self.lboctd_value_recurring
        sale = self.env['sale.order'].browse(self.env.context.get('active_id'))
        risk_reserve_order_amt = 0
        monthly_recurring_val = 0
        yearly_recurring_val = 0
        for item in sale.order_line:
            if item.product_template_id.x_studio_service_type == 'Risk Reserve' or item.product_template_id.x_studio_service_type == 'Enhancement Risk Reserve':
                risk_reserve_order_amt += item.price_unit
            if item.product_template_id.x_studio_service_type == 'Base Plan' or item.product_template_id.x_studio_service_type == 'Enhancements':
                monthly_recurring_val += item.price_unit
            if item.product_template_id.x_studio_service_type == 'Base Plan' or item.product_template_id.x_studio_service_type == 'Enhancements':
                yearly_recurring_val += item.price_unit
        if consolatory_value_recurring > 0 and orderval_afterconsol_recurring > 0 or lboctd_value_recurring > 0 and orderval_afterconsol_recurring > 0 or consolatory_value_recurring > 0 and lboctd_value_recurring > 0:
            raise UserError('Only one (recurring) field can have a value.')
        else:
            if lboctd_rr_waiver and rr_waiver_ammount > 0 and risk_reserve_order_amt > 0:
                res = [{
                    'product_id' :	59322,
                    'name' : 'Consolatory Benifit (Risk Reserve Waiver)',
                    'sequence' : 40,
                    'price_unit' : -rr_waiver_ammount
                }]
                    
        
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
                
            elif lboctd_rr_waiver and risk_reserve_order_amt > 0:
                res = [{
                    'product_id' :	59322,
                    'name' : 'Consolatory Benifit (Risk Reserve Waiver)',
                    'sequence' : 40,
                    'price_unit' : -risk_reserve_order_amt
                }]
                    
        
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
            
            if sale.x_studio_payment_mode.id == 3 and lboctd_value_recurring > 0 and monthly_recurring_val > 0:
                
                res = [{
                    'product_id' :	59314,
                    'sequence' : 40,
                    'price_unit' : lboctd_value_recurring - monthly_recurring_val
                }]
                    
        
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
            
            if sale.x_studio_payment_mode.id == 6 and lboctd_value_recurring > 0 and yearly_recurring_val > 0:
                
                res = [{
                    'product_id' :	59315,
                    'sequence' : 40,
                    'price_unit' : lboctd_value_recurring - yearly_recurring_val
                }]
                
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
            
            if sale.x_studio_payment_mode.id == 3 and consolatory_value_recurring > 0 and monthly_recurring_val > 0:
                
                res = [{
                    'product_id' :	59320,
                    'sequence' : 40,
                    'price_unit' : -consolatory_value_recurring
                }]
                    
        
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
            
            if sale.x_studio_payment_mode.id == 6 and consolatory_value_recurring > 0 and yearly_recurring_val > 0:
                
                res = [{
                    'product_id' :	59321,
                    'sequence' : 40,
                    'price_unit' : -consolatory_value_recurring
                }]
                    
        
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
            
            if sale.x_studio_payment_mode.id == 3 and orderval_afterconsol_recurring > 0 and monthly_recurring_val > 0:
                
                res = [{
                    'product_id' :	59320,
                    'sequence' : 40,
                    'price_unit' : orderval_afterconsol_recurring - monthly_recurring_val
                }]
                    
        
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
            
            if sale.x_studio_payment_mode.id == 6 and orderval_afterconsol_recurring > 0 and yearly_recurring_val > 0:
                
                res = [{
                    'product_id' :	59321,
                    'sequence' : 40,
                    'price_unit' : orderval_afterconsol_recurring - yearly_recurring_val
                }]
                
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
            
            if registration_package:
                res = [{
                    'product_id' :	59317,
                    'sequence' : 50
                }]
                    
        
                sale.write({'order_line': [(0, 0, vals) for vals in res]})
            
            if onboarding_package:
                res = [{
                    'product_id' :	59316,
                    'sequence' : 50
                }]
                    
        
                sale.write({'order_line': [(0, 0, vals) for vals in res]})

                