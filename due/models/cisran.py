from random import choice
from string import digits
from odoo import fields, models
from odoo.exceptions import ValidationError, AccessError

class Partner(models.Model):
    _inherit = "res.partner"
    
    x_cisran = fields.Char(string='CIS RAN', compute='_generate_cisran')
    
    _sql_constraints = [
        ('cisran_unique', 'unique (x_cisran)', "The CISRANID must be unique, this one is already assigned to another Member.") 
    ]
    
    def _generate_cisran(self):
        for partner in self:
            partner.x_cisran = 'R'+"".join(choice(digits) for i in range(11))
