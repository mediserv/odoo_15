# -*- coding: utf-8 -*-
###################################################################################
#    
#
###################################################################################

{
    'name': 'Coverage Period Followup',
    'version': '14.0.1.0.0',
    'author': 'Centralasis Proactive Solutions',
    'maintainer': 'Centralasis Proactive Solutions',
    'company': 'Centralasis Proactive Solutions',
    'website': 'https://www.centralasis.com',
    'depends': ['account', 'mail', 'sms', 'account_reports', 'base', 'hr_payroll', 'sale_management', 'sale_subscription',
                ],
    'data': [ 	'security/ir.model.access.csv',
                'wizard/auxillary_package.xml',
                'wizard/upgrade_downgrade.xml',
                'views/due_subscription_form.xml',
            	
            ],
    'qweb': [
        "static/src/xml/account_reconciliation.xml",
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'AGPL-3',
}
