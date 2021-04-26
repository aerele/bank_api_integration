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
		});}
});
