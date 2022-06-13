from odoo import models, fields, api, _

class Document(models.Model):
    _name = 'documents.document'
    _inherit = 'documents.document'
    
    
    claim_id = fields.Many2one('claims.form', string='Claim', readonly=True, tracking=True)

