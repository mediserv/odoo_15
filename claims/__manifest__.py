# -*- coding: utf-8 -*-
###################################################################################
#    
#
###################################################################################

{
    'name': 'Claims Module',
    'version': '14.0.1.0.0',
    'author': 'Centralasis Proactive Solutions',
    'maintainer': 'Centralasis Proactive Solutions',
    'company': 'Centralasis Proactive Solutions',
    'website': 'https://www.centralasis.com',
    'depends': ['account', 'mail', 'sms', 'account_reports', 'base', 'hr_payroll', 'sale_management', 'sale_subscription','due',
                ],
    'data': [ 	'security/ir.model.access.csv',
                 'wizard/account_move_contra_wizard.xml',
                 'views/account_move.xml',
                 'views/claims_view.xml',
                 'data/ir_sequence_data.xml'
    		   
            ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'AGPL-3',
}
