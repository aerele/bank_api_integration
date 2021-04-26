// Copyright (c) 2019, Aerele Technologies Private Limited and contributors
// For license information, please see license.txt
frappe.ui.form.on(cur_frm.doctype,{
    onload: function(frm) {
        frm.set_query("company_bank_account", function() {
			return {
				"filters":{
					"is_company_account": 1,
					"company":frm.doc.company
				},
			};
		});
    }})