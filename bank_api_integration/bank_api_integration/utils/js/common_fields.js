// Copyright (c) 2019, Aerele Technologies Private Limited and contributors
// For license information, please see license.txt
frappe.ui.form.on(cur_frm.doctype,{
    onload: function(frm) {
        frm.set_query("company_bank_account", function() {
			return {
				query: "bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.get_company_bank_account",
				filters: {
					"company":frm.doc.company,
					"is_company_account": 1
				}
			};
		});
    }})