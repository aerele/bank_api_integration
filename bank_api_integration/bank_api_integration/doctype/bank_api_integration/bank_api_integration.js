// Copyright (c) 2021, Aerele and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bank API Integration', {
	onload: function(frm) {
        frm.set_query("bank_account", function() {
			return {
				"filters":{
					"is_company_account": 1
				},
			};
		});},
	fetch_balance: function(frm){
		frappe.call({
			method: "bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.fetch_balance",
			freeze: true,
			args: {doc_name: frm.doc.name},
			callback: function(r) {
				if(r.message) {
				frm.set_value('balance_amount',r.message);
				}
			}
				});
		frm.save();
		}
});
