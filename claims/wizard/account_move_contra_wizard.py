from odoo.exceptions import UserError
from odoo import models, fields, api, _


class AccountMoveContraWizard(models.TransientModel):
    _name = 'account.move.contra.wizard'
    _description = 'Claims offset wizar'
    
    def _default_journal_entry(self):
        return self.env['account.move'].browse(self._context.get('active_id'))

    journal_entry_id = fields.Many2one('account.move', string="Journal Entry", required=True,
                                      default=_default_journal_entry, ondelete="cascade")
    date = fields.Date(string="Date", required=True )
    amount = fields.Float(string="Amount", required=True)
    member = fields.Many2one('res.partner', string="Member", required=True)
    claim_numbers = fields.Char(string="Claim Numbers", required=True)
    
    def proceed(self):
        date = self.date
        ammount = self.amount
        member = self.member
        claim_numbers = self.claim_numbers
        
        
        res = []
        journal_entry = self.env['account.move'].browse(self.env.context.get('active_id'))
              
        res= [{
                    'account_id' :	175,
                    'name' : 'Claims Offset ' + claim_numbers,
                    'partner_id' : member.id,
                    'credit' : ammount,
                },
                {
                    'account_id' :	261,
                    'name' : 'Claims Offset' + claim_numbers,
                    'partner_id' : member.id,
                    'debit' : ammount,
                },
        ]
        journal_entry.write({'line_ids': [(0, 0, vals) for vals in res],
                            'journal_id' : 29,
                            'date' : date})
