from odoo import models, fields, api, _

class ClaimsForm(models.Model):
    _name = 'claims.form'
    _description = 'Claims Form'
    _inherit = ['mail.thread', 'documents.mixin']
    _check_company_auto = True
    
    name = fields.Char(string="Claim", readonly=True, copy=False, compute='_compute_name')
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, default=lambda self: self.env.company)
    date_received = fields.Date(string="Date Received", required=True)
    expected_payment_date = fields.Date(string="Expected Payment Date",)
    office_received = fields.Selection(string='Receiving Location', selection=[('sando', 'San Fernando'), ('pos', 'Port of Spain'), ('point', 'Point Fortin')], required=True)
    delivery_mode = fields.Selection(string='Mode of Delivery', selection=[('mail','Mail'),('dropbox','Drop Box'), ('personal_dropin','Personal Drop in'),], required=True)
    user_id = fields.Many2one('res.users', string="Receiving Employee", readonly=True, default=lambda self: self.env.user.id)
    claim_number = fields.Char(string='Claim Number', readonly=True, copy=False)
    claim_category = fields.Selection(string=' Claim Category', selection=[('d', 'Dental'), ('v', 'Vision'), ('p', 'Maternity'),('m', 'Medical'), ('e', 'Death'), ('s', 'Preventative Screening'), ('pi', 'Physical Injury')], required=True)
    member_id = fields.Many2one('res.partner', string='Member', required=True)
    dependent_id = fields.Many2one('res.partner', string='Dependent')
    diagnosis = fields.Char(string='Diagnosis', required = True)
    underlying_illness = fields.Char(string='Underlying Illness', required = True)
    state = fields.Selection(string='Claim Stages', selection=[('to_submit', 'To Submit'), ('complete', 'Complete'), ('pending', 'Pending'), ('hold', 'Hold'), ('recommend_approve', 'Recommend to Approve'), ('recommend_decline', 'Recommend to Decline'), ('discuss', 'Discus'), ('arbitrate', 'Arbitrate'), ('review', 'Review'), ('decline', 'Decline'), ('approve', 'Approve'), ], default='to_submit', copy=False)
    claim_documents_ids = fields.One2many('claim.documents','claims_form_id', copy=True, auto_join=True)
    claim_items_ids = fields.One2many('claim.items','claims_form_id', states={'approve': [('readonly', True)]}, copy=True, auto_join=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, string='Currency', readonly=True)
    total_claim_amount = fields.Monetary(string='Claim amount', copy=False, readonly=True, compute='_amount_total')
    total_approved_amount = fields.Monetary(string='Approved Amount', copy=False, readonly=True, compute='_amount_total')
    claim_bill = fields.Many2one('account.move', string='Claim bill', copy=False, readonly=True)
    payment_state = fields.Selection(string='Payment stage', selection=[('paid','Paid'),('in_payment','In Payment'), ('partial','Partial')], compute='_payment_state', copy=False)
    ran = fields.Char(string="RAN", related='member_id.x_cisran', readonly=True)
    old_ran = fields.Char(string="OLD RAN", related='member_id.x_studio_ran_number_1', readonly=True)
    plan_base_code = fields.Many2one('product.template', string="Base Plan Code", domain='[["x_studio_service_type","=","Base Plan"]]')
    plan_base_sumassured = fields.Monetary(string="Base Plan Sum Assured", readonly=True,)
    baseplan_commencement_date = fields.Date(string="Base Plan Commencemnt Date")
    enhancement_code = fields.Many2one('product.template', string="Enhancement Plan Code")
    enhancement_commencement_date = fields.Date(string="Enhancement Commencemnt Date")
    enhancement_sumassured = fields.Monetary(string="Enhancement Sum Assured", )
    contract_version = fields.Char(string="Contract Version number")
    p_initial_commencement_date = fields.Date(string="Principal's Initial Commencemnt Date", required=True)
    d_initial_commencement_date = fields.Date(string="Dependent's Initial Commencemnt Date",)
    principal_dob = fields.Date(string="Principal DOB", related='member_id.x_studio_date_of_birth', readonly=True)
    dependent_dob = fields.Date(string="Dependent DOB", compute='_compute_dob_comencment_date', readonly=True)
    submitted = fields.Boolean('Submitted')
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, string='Currency', readonly=True)
    claim_made_against = fields.Selection(string='Claim Made Against', selection=[('base_plan', 'Base Plan Only'), ('enhancement', 'Enchancement Only'), ('base_and_enchancement', 'Both Base Plan and Enhancement')])
    
    
    _sql_constraints = [
        ('claim_number_unique', 'unique (claim_number)', "The Claim Number must be unique, this one is already assigned to another Claim.")]
    
    
    @api.depends('claim_bill.payment_state',)
    def _payment_state(self):
        claim_bill = self.claim_bill
        if claim_bill:
            for claim in self:
                if claim.claim_bill.payment_state == 'paid':
                    claim.payment_state = 'paid'
                elif claim.claim_bill.payment_state == 'in_payment':
                    claim.payment_state = 'in_payment'
                elif claim.claim_bill.payment_state == 'partial':
                    claim.payment_state = 'partial'
                else:
                    claim.payment_state = None
        else:
            for claim in self:
                claim.payment_state = None
    
    @api.depends('dependent_id.x_studio_date_of_birth')
    def _compute_dob_comencment_date(self):
        for claim in self:
            if claim.dependent_id.x_studio_date_of_birth:
                claim.dependent_dob = claim.dependent_id.x_studio_date_of_birth
            else:
                claim.dependent_dob  = None
            
    
    
    
    @api.depends('claim_items_ids.claim_amount', 'claim_items_ids.approved_amount')
    def _amount_total(self):
       
        for claim in self:
            total_claim_ammount = 0
            total_approved_ammount = 0
            for line in claim.claim_items_ids:
                total_claim_ammount += line.claim_amount
                total_approved_ammount += line.approved_amount
            claim.update({
                'total_claim_amount': total_claim_ammount,
                'total_approved_amount': total_approved_ammount,
            })
    
    def _compute_name(self):
        for line in self:
            if line.member_id and not line.claim_number:
                line.name = line.member_id.name + ' - To Submit'
            elif line.member_id and line.claim_number:
                line.name = line.member_id.name + ' - ' + line.claim_number
    
    
    def create_bill(self):
        bill_move = self.env['account.move'].with_context(move_type='in_invoice', company_id=self.company_id).with_company(self.company_id)
        company = self.env.company
        
        bill = {
            'move_type': 'in_invoice',
            'partner_id': self.member_id,
            'currency_id': self.currency_id,
            'journal_id': 24,
            'invoice_date_due': self.expected_payment_date,
            'invoice_date' : self.expected_payment_date,
            'invoice_user_id': self.user_id.id,
            'partner_bank_id': company.partner_id.bank_ids.filtered(lambda b: not b.company_id or b.company_id == company)[:1].id,
            'ref' : self.claim_number,
        }
        bill_lines = {
            'name': 'Claim - ' + self.claim_number,
            'price_unit': self.total_approved_amount or 0.0,
            'quantity': 1,
        
        }
        bill['invoice_line_ids'] = [(0, 0, bill_lines)]
        new_bill = bill_move.create(bill)
        self.write({'claim_bill' : new_bill })
        if new_bill.state != 'posted':
            new_bill._post(False)
            new_bill.is_move_sent = True

    
    def approve(self):
        self.write({'state' : 'approve' })
    def decline(self):
        self.write({'state' : 'decline' })
    def discuss(self):
        self.write({'state' : 'discuss' })
    def arbitrate(self):
        self.write({'state' : 'arbitrate' })
    def pending(self):
        self.write({'state' : 'pending' })
    def hold(self):
        self.write({'state' : 'hold' })
    def recommend_approve(self):
        self.write({'state' : 'recommend_approve' })
    def recommend_decline(self):
        self.write({'state' : 'recommend_decline' })
    def summit(self):
        
        self.write({'state' : 'complete' })
        if self.claim_category ==  'd':
            self.write({'claim_number' : self.env['ir.sequence'].next_by_code('d.dental')})
        if self.claim_category ==  'v':
            self.write({'claim_number' : self.env['ir.sequence'].next_by_code('v.vision')})
        if self.claim_category ==  'p':
            self.write({'claim_number' : self.env['ir.sequence'].next_by_code('p.maternity')})
        if self.claim_category ==  'm':
            self.write({'claim_number' : self.env['ir.sequence'].next_by_code('m.medical')})
        if self.claim_category ==  'e':
            self.write({'claim_number' : self.env['ir.sequence'].next_by_code('e.death')})
        if self.claim_category ==  's':
            self.write({'claim_number' : self.env['ir.sequence'].next_by_code('s.preventative.screening')})
        if self.claim_category ==  'pi':
            self.write({'claim_number' : self.env['ir.sequence'].next_by_code('pi.physical_injury')})
            
    document_count = fields.Integer('Document Count', compute='_compute_document_count')

    def _compute_document_count(self):
        read_group_var = self.env['documents.document'].read_group(
            [('partner_id', '=', self.member_id.ids), ('folder_id', '=', self.env.ref('claims.documents_claims_folder').id), ('claim_id', '=', self.id)],
            fields=['partner_id'],
            groupby=['partner_id'])

        document_count_dict = dict((d['partner_id'][0], d['partner_id_count']) for d in read_group_var)
        test = None
        for record in self.member_id:
            test = document_count_dict.get(record.id, 0)
        for record in self:
            record.document_count = test
    
    
    
    def action_see_documents(self):
        self.ensure_one()
    
        return {
            'name': _('Documents'),
            'res_model': 'documents.document',
            'type': 'ir.actions.act_window',
            'views': [(False, 'kanban'), (False, 'list')],
            'view_mode': 'kanban',
            'context': {
                "search_default_partner_id": self.member_id.id,
                "search_default_claim_id": self.id,
                "default_partner_id": self.member_id.id,
                "claim_id" : self.id,
                "searchpanel_default_folder_id": self.env.ref('claims.documents_claims_folder').id,
                
            },
        }
    
    
    
    def _get_document_vals(self, attachment):
        """
        Return values used to create a `documents.document`
        """
        self.ensure_one()
        document_vals = {}
        document_vals = {
            'attachment_id': attachment.id,
            'name': attachment.name or self.display_name,
            'folder_id': self.env.ref('claims.documents_claims_folder').id,
            'owner_id': self._get_document_owner().id,
            'tag_ids': [(6, 0, self._get_document_tags().ids)],
            'partner_id': self._get_document_partner().id,
            'claim_id' : self._get_document_claim_id().id,
            }
        return document_vals
    


    
    def _get_document_claim_id(self):
        return self
    def _get_document_partner(self):
        return self.member_id
    


            
class ClaimDocuments(models.Model):
    _name = "claim.documents"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Documents for Claims"
    _order = "date_received desc"
    _check_company_auto = True
    
    name = fields.Char(string="Name", copy=False,)
    date_received = fields.Date(string="Date Received", required=True, copy=False)
    company_id = fields.Many2one('res.company', related='claims_form_id.company_id', string='Company', store=True, readonly=True, index=True, copy=False )
    member_id = fields.Many2one('res.partner', related='claims_form_id.member_id', store=True, string='Member', readonly=False, copy=False)
    dependent_id = fields.Many2one('res.partner', related='claims_form_id.dependent_id', store=True, string='Dependent', readonly=False, copy=False)
    claims_form_id = fields.Many2one('claims.form', string='claims form', required=True, ondelete='cascade', index=True, copy=False)
    
    
    
class ClaimItems(models.Model):
    _name = "claim.items"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Claim Items and amounts"
    _order = "id desc"
    _check_company_auto = True
    
    name = fields.Char(string="Base Benefits", copy=False,)
    company_id = fields.Many2one('res.company', related='claims_form_id.company_id', string='Company', store=True, readonly=True, index=True, copy=False )
    member_id = fields.Many2one('res.partner', related='claims_form_id.member_id', store=True, string='Member', readonly=False, copy=False)
    dependent_id = fields.Many2one('res.partner', related='claims_form_id.dependent_id', store=True, string='Dependent', readonly=False, copy=False)
    claims_form_id = fields.Many2one('claims.form', string='claims form', required=True, ondelete='cascade', index=True, copy=False)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, string='Currency', readonly=True)
    claim_amount = fields.Monetary(string='Claim amount', copy=False)
    approved_amount = fields.Monetary(string='Approved Amount', copy=False)
    state = fields.Selection(string='Claim Stages', selection=[('to_submit', 'To Submit'), ('complete', 'Complete'), ('pending', 'Pending'), ('hold', 'Hold'), ('recommend_approve', 'Recommend to Approve'), ('recommend_decline', 'Recommend to Decline'), ('discuss', 'Discus'), ('arbitrate', 'Arbitrate'), ('review', 'Review'), ('decline', 'Decline'), ('approve', 'Approve'), ], related='claims_form_id.state', copy=False)
    
    

    
