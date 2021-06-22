frappe.ui.form.on("Bank Account", {
	fetch_balance: function(frm){
		frappe.call({
			method: "bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.fetch_balance",
			freeze: true,
			args: {bank_account: frm.doc.name},
			callback: function(r) {
				frm.reload_doc();
			}
		})
	},
	fetch_account_statement: function(frm){
		frappe.call({
			method: "bank_api_integration.bank_api_integration.doctype.bank_api_integration.bank_api_integration.fetch_account_statement",
			freeze: true,
			args: {bank_account: frm.doc.name},
			callback: function(r) {
				frm.reload_doc();
			}
		})
	}
})