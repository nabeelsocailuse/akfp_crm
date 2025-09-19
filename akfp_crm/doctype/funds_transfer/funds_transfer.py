# Developer Aqsa Abbasi
import frappe
from frappe.model.document import Document
import json
import datetime
from erpnext.accounts.utils import get_fiscal_year
from frappe.utils import (
    today, fmt_money, get_link_to_form
)
from akf_projects.customizations.overrides.project.financial_stats import get_transactions

# from frappe import today

class FundsTransfer(Document):
	def validate(self):
		self.posting_date = today()
		self.validate_cost_center()
		self.validate_inter_branch_accounts()
		self.validate_inter_bank()
		self.donor_list_data_funds_transfer(is_valid=True)
		self.update_funds_tranfer_from()
		self.set_deduction_breakeven()
		self.calculate_totals()

	def validate_cost_center(self):
		if self.transaction_type == 'Inter Branch':
			if self.from_cost_center == self.to_cost_center:
				frappe.throw("Cost Centers cannot be same in Inter Branch Transfer")

	def validate_inter_branch_accounts(self):
		if self.transaction_type == 'Inter Branch':
			if self.from_bank_account == self.to_bank_account:
				frappe.throw("Banks cannot be same in Inter Branch Transfer")
			if (not self.desposit_in_transit_account or not self.ibft_equity_account):
				clink = get_link_to_form("Company", self.company)
				frappe.throw(f"[Desposit In Transit Account, IBFT (Equity) Account] are need to be set in company {clink}", title="Inter Branch (Accounts Settings)")

	def validate_inter_bank(self):
		if self.transaction_type == 'Inter Bank':
			if self.account_balance_from <= 0.0:
				frappe.throw(f"ZERO balance in {self.from_bank}", title="No Balance")
			if self.account_balance_from < self.transfer_amount :
				frappe.throw(f"Transfer amount <b>{self.transfer_amount}</b> is greater than available balance <b>{self.account_balance_from}</b>", title="Exceeding balance")
 
	@frappe.whitelist()
	def update_funds_tranfer_from(self):
		ftf_dict = frappe._dict()

		for row in self.funds_transfer_to:
			amount = row.ft_amount

			if(row.ft_donor in ftf_dict): 
				ftf_dict[f'{row.ft_donor}'] += amount
			else: 
				ftf_dict.update({f'{row.ft_donor}': amount})
			
			if(amount<=0.0):
				frappe.throw(f"""In <b>Row#{row.idx}</b>, the amount cannot be negative or zero to transfer.""", 
					title="Funds Transfer To")
		
		for donorId in ftf_dict:
			IS_DONOR = False
			transfer_amount = ftf_dict[donorId]
			for row in self.funds_transfer_from:
				if(donorId == row.ff_donor):
					balance_amount = row.ff_balance_amount
					if(transfer_amount > balance_amount):
						actualMoney = fmt_money(balance_amount, currency="PKR")
						transferMoney = fmt_money(transfer_amount, currency="PKR")
						extraMoney = fmt_money((transfer_amount - balance_amount), currency="PKR")
						frappe.throw(f"""In <b>Row#{row.idx}</b>, the balance amount is <b>{actualMoney}</b> and you're transfering <b>{transferMoney}</b> with extra of <b>{extraMoney}</b>.""", 
							title="Funds Transfer From")
					
					row.ff_transfer_amount = transfer_amount
					row.transfer = True
					IS_DONOR = True
			
			if(not IS_DONOR):
				frappe.throw(f"""Donor <b>{donorId}</b> not found in <b>Funds Tranfer From`</b> table.""" , title="Funds Transfer To")
		
		# for row1 in self.funds_transfer_to:
		# 	actual_balance = 0.0
		# 	is_found = True
		# 	donor_not_found = True
		# 	remaining_balance = row1.ft_amount
		# 	# if user enters -ve or zero values.
		# 	if(remaining_balance<=0.0):
		# 		frappe.throw(f"""In <b>Row#{row1.idx}</b>, the amount cannot be negative or zero to transfer.""", 
		# 			title="Funds Transfer To")
				
		# 	for row2 in self.funds_transfer_from:
		# 		balance_amount = row2.ff_balance_amount
		# 		if(row1.ft_donor == row2.ff_donor):
		# 			row2.ff_transfer_amount = 0.0
		# 			row2.transfer = 0
		# 			if (remaining_balance>0.0) and (remaining_balance<=balance_amount) and (is_found):
		# 				row2.ff_transfer_amount = remaining_balance
		# 				remaining_balance -= remaining_balance
		# 				row2.transfer = 1
		# 				is_found = False
		# 			elif(remaining_balance>row2.ff_balance_amount):
		# 				row2.ff_transfer_amount = balance_amount
		# 				remaining_balance -= balance_amount
		# 				row2.transfer = 1
		# 			actual_balance += balance_amount
		# 			donor_not_found = False
			
		# 	if(donor_not_found):
		# 		frappe.throw(f"""In <b>Row#{row1.idx}</b>,  Donor <b>{row1.ft_donor_name}</b> not found in <b>Funds Tranfer From`</b> table.""" , title="Funds Transfer To")
			
		# 	if(remaining_balance>0.0):
		# 		actualMoney = fmt_money(actual_balance, currency="PKR")
		# 		transferMoney = fmt_money(row1.ft_amount, currency="PKR")
		# 		remainingMoney = fmt_money(remaining_balance, currency="PKR")
		# 		frappe.throw(f"""In <b>Row#{row1.idx}</b>, the actual amount is <b>{actualMoney}</b> and you're transfering <b>{transferMoney}</b> with extra of <b>{remainingMoney}</b>.""", 
		# 			title="Funds Transfer To")
			
	@frappe.whitelist()
	def set_deduction_breakeven(self):
		if(self.transaction_type=='Inter Branch'): 
			from akf_accounts.akf_accounts.doctype.funds_transfer.deduction_breakeven import apply_deduction_breakeven
			apply_deduction_breakeven(self)
		else: self.set("deduction_breakeven", [])

	def calculate_totals(self):
		self.total_amount = sum(d.ft_amount for d in self.funds_transfer_to)
		self.total_deduction = sum(d.amount for d in self.deduction_breakeven)
		self.outstanding_amount = (self.total_amount - self.total_deduction)

	@frappe.whitelist()
	def donor_list_data_funds_transfer(self, is_valid=False):
		def validate_missing_info(row):
			conditions = ""
			for field1, field2 in [
				('subservice_area', "ff_subservice_area"),
				('donor', "ff_donor"),
				('project', "project"),
				('cost_center', "ff_cost_center"),
				('product', "ff_product"),
				('service_area', "ff_service_area"),
				('company', "ff_company"),
				('account', "ff_account")]:
				value2 = row.get(field2)
				if(value2):
					conditions += f" and {field1} = '{value2}' "
				else:
					label =  field2.replace("ff_", "")
					label =  label.replace("_", " ")
					frappe.msgprint(f"Row#{row.idx}, please select <b>{label.capitalize()}</b>", title="Funds Transfer From")
			return conditions

		def get_donor_entries(condition):
			""" sql by nabeel saleem """
			query = f"""  Select 
					ifnull((sum(distinct gl.credit) - sum(distinct gl.debit)),0) as total_balance,
					gl.donor,
					(select donor_name from `tabDonor` where name=gl.donor) as donor_name,
					gl.service_area,
					gl.subservice_area,
					gl.project,
					gl.cost_center,
					gl.product,
					gl.company,
					gl.account
				From 
					`tabGL Entry` gl, `tabDonation` d, `tabFunds Transfer` ft
				Where 
					(gl.voucher_no = d.name or gl.voucher_no = ft.name)
					and d.contribution_type ='Donation'
					and gl.is_cancelled=0
					and voucher_type  in ('Donation', 'Funds Transfer')
					and gl.account in (select name from `tabAccount` where disabled=0 and account_type='Equity' and name=gl.account)
					{f'{condition}' if condition else ''}
				Having 
					total_balance>0
				Order By 
					total_balance desc
				"""
			return frappe.db.sql(query, as_dict=True)

				
		def validate_duplicates(row, entry_key, duplicate_entries):
			if(entry_key in duplicate_entries):
				if(is_valid):
					frappe.throw(f'In <b>Row#{row.idx}</b>; duplicate entry exists for donor "{row.ff_donor}" with provided details.</span>', title="Funds Transfer From")
				else:
					frappe.msgprint(f'In <b>Row#{row.idx}</b>; duplicate entry exists for donor "{row.ff_donor}" with provided details.</span>', title="Funds Transfer From")

		def validate_balance(row, financial_stats):
				remaining_amount = financial_stats['remaining_amount'] 
				if(remaining_amount<=0.0): 
					row.ff_balance_amount = 0.0
					if(is_valid):
						frappe.throw(f"""<b>Row#{row.idx}</b>; no balance exists for <b>{row.ff_donor}</b> with provided details""", 
								title="Funds Transfer From")
					else:
						frappe.msgprint(f"""<b>Row#{row.idx}</b>; no balance exists for <b>{row.ff_donor}</b> with provided details""", 
								title="Funds Transfer From")
				else:
					row.ff_balance_amount = remaining_amount

		def execute_funds_transfer_from():
			duplicate_entries = set()
			filters = set()
			for row in self.funds_transfer_from:
				# validate_missing_info(row) # If some filters are missed
				entry_key = (
					row.ff_company,
					row.ff_cost_center,
					row.ff_service_area,
					row.ff_subservice_area,
					row.ff_product,
					row.project,
					row.ff_donor,
					row.ff_account,
				)
				validate_duplicates(row, entry_key, duplicate_entries) # If same filters in new row
				duplicate_entries.add(entry_key) # update set of duplicate entries
				filters = {
					'subservice_area': row.ff_subservice_area,
					'donor': row.ff_donor,
					'project': row.project,
					'cost_center': row.ff_cost_center,
					'product': row.ff_product,
					'service_area': row.ff_service_area,
					'company': row.ff_company,
					'account': row.ff_account
				}
				financial_stats = get_transactions(filters) # get complete stats
				validate_balance(row, financial_stats) # validate balance against filters
				# donor_entries = get_donor_entries(condition)
	
		if(self.docstatus==0): execute_funds_transfer_from()

	def on_update(self): 
		if ((self.from_gl_entry) and (not self.to_gl_entry)): self.make_gl_entries()

	def on_submit(self):
		transaction_types = ['Inter Branch', 'Inter Fund', 'Inter Bank']
		if self.transaction_type in transaction_types:
			self.make_gl_entries()
			# self.create_gl_entries_for_inter_funds_transfer()
		if(self.transaction_type == 'Inter Branch'): 
			from akf_accounts.akf_accounts.doctype.funds_transfer.deduction_breakeven import make_deduction_gl_entries
			make_deduction_gl_entries(self)

	def on_trash(self):
		self.delete_all_gl_entries()

	def on_cancel(self):
		self.delete_all_gl_entries()

	def delete_all_gl_entries(self):
		frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", self.name)
		if(hasattr(self, 'workflow_state')): 
			frappe.db.set_value(self.doctype, self.name, 'workflow_state', 'Cancelled') 
			self.reload

	def make_gl_entries(self):
		
		def validate_funds_transfer_to():
			if (not self.funds_transfer_to and self.transaction_type!="Inter Bank"):
				frappe.throw("There is no information to transfer funds.", title="Funds Transfer To")
				
		# make debit entries
		def gl_entries_funds_transfer_from():
			args = _get_gl_structure(self)
			for row in self.funds_transfer_from:
				# Debit entry for previous dimension; funds transfer from
				if(row.transfer):
					args = _get_gl_structure(self)
					args.update({
						'account': row.ff_account,
						'party_type': 'Donor',
						'party': row.ff_donor,
						'cost_center': row.ff_cost_center,
						'against': row.ff_account,
						'company': row.ff_company,
						'project': row.project,
						'service_area': row.ff_service_area,
						'subservice_area': row.ff_subservice_area,
						'product': row.ff_product,      
						'donor': row.ff_donor, 
						# 
						'debit': row.ff_transfer_amount,
						'debit_in_account_currency': row.ff_transfer_amount,
						'debit_in_transaction_currency': row.ff_transfer_amount,
					})
					doc = frappe.get_doc(args)
					doc.insert(ignore_permissions=True)
					doc.submit()

					if(self.transaction_type != "Inter Bank"):
						if(self.from_gl_entry and not self.to_gl_entry):
							# def entry_Deposit_In_Transit():
							if(self.transaction_type in ["Inter Branch"]):
								args.update({
									'account': self.desposit_in_transit_account,
									'cost_center': self.from_cost_center,
									'against': self.desposit_in_transit_account,

								})
								doc = frappe.get_doc(args)
								doc.insert(ignore_permissions=True)
								doc.submit()
							
								# def entry_IBFT_Equity():
								args.update({
									'account': self.ibft_equity_account,
									'cost_center': self.from_cost_center,
									'against': self.ibft_equity_account,
									'credit': row.ff_transfer_amount,
									'credit_in_account_currency': row.ff_transfer_amount,						
									'credit_in_transaction_currency': row.ff_transfer_amount,
									'debit': 0,
									'debit_in_account_currency': 0,
									'debit_in_transaction_currency': 0
								})
								doc = frappe.get_doc(args)
								doc.insert(ignore_permissions=True)
								doc.submit()
			
		# make credit entries
		def gl_entries_funds_transfer_to():
			for row in self.funds_transfer_to:
				# for bank from gl entry purpose
				# sum_ft_amount += row.ft_amount
				# Debit entry for previous dimension; funds transfer from
				amount = row.outstanding_amount if(row.outstanding_amount>0) else row.ft_amount
				args = _get_gl_structure(self)
				args.update({
					'account': row.ft_account,
					'against': row.ft_account,
					'party_type': 'Donor',
					'party': row.ft_donor,
					'cost_center': row.ft_cost_center,
					# 
					'credit': amount,
					'credit_in_account_currency': amount,
					'credit_in_transaction_currency': amount,
					# 
					'project': row.project,
					'fund_class': row.fund_class if(self.transaction_type != "Inter Bank") else "",
					'service_area': row.ft_service_area,
					'subservice_area': row.ft_subservice_area,
					'product': row.ft_product,      
					'donor': row.ft_donor	
				})
				doc = frappe.get_doc(args)
				doc.insert(ignore_permissions=True)
				doc.submit()

				if(self.transaction_type !="Inter Bank"):
					if(self.to_gl_entry):
						# def entry_Deposit_In_Transit():
						if(self.transaction_type in ["Inter Branch"]):
							args.update({
								'account': self.desposit_in_transit_account,
								'cost_center': self.from_cost_center,
								'against': self.desposit_in_transit_account,
								# 
								'credit': row.ft_amount,
								'credit_in_account_currency': row.ft_amount,
								'credit_in_transaction_currency': row.ft_amount,
								#
							})
							doc = frappe.get_doc(args)
							doc.insert(ignore_permissions=True)
							doc.submit()
							# def entry_IBFT_Equity():
							args.update({
								'account': self.ibft_equity_account,
								'cost_center': self.from_cost_center,
								'against': self.ibft_equity_account,
								'debit': row.ft_amount,
								'debit_in_account_currency': row.ft_amount,					
								'debit_in_transaction_currency': row.ft_amount,
								'credit': 0,
								'credit_in_account_currency': 0,
								'credit_in_transaction_currency': 0
							})
							doc = frappe.get_doc(args)
							doc.insert(ignore_permissions=True)
							doc.submit()
			# return sum_ft_amount
		
		# make credit entries
		def gl_entry_bank_from():
			from_bank = None
			# if(not self.from_bank) and (self.transaction_type=='Inter Fund'): return
			if(self.transaction_type=='Inter Fund'): return
			if(not self.from_bank_account) and (self.transaction_type=='Inter Branch'): return
			if(self.from_bank): from_bank = self.from_bank
			if(self.from_bank_account): from_bank = self.from_bank_account
			# Credit entry for bank account	
			args = _get_gl_structure(self)
			amount = self.transfer_amount if(self.transaction_type=='Inter Bank') else self.total_amount
			args.update({
				'account': from_bank,
				'cost_center': self.from_cost_center if(self.transaction_type == "Inter Branch") else self.cost_center,
				'against': from_bank,			
				'credit': amount,
				'credit_in_account_currency': amount,						
				'credit_in_transaction_currency': amount
			})
			doc = frappe.get_doc(args)
			doc.insert(ignore_permissions=True)
			doc.submit()
			# In transit bank entry debit
			entry_Deposit_In_Transit()
		
		# make debit entries
		def gl_entry_bank_to():
			to_bank = None
			# if(not self.to_bank) and (self.transaction_type=='Inter Fund'): return
			if(self.transaction_type=='Inter Fund'): return
			if(not self.to_bank_account) and (self.transaction_type=='Inter Branch'): return
			if(self.to_bank): to_bank = self.to_bank
			if(self.to_bank_account): to_bank = self.to_bank_account
			
			# In transit bank entry credit
			entry_Deposit_In_Transit()
			# Debit entry for bank account
			args = _get_gl_structure(self)
			amount = self.transfer_amount if(self.transaction_type=='Inter Bank') else self.total_amount
			args.update({
				'account': to_bank,
				'cost_center': self.to_cost_center if(self.transaction_type == "Inter Branch") else self.cost_center,
				'against': to_bank,			
				'debit': amount,
				'debit_in_account_currency': amount,
				'debit_in_transaction_currency': amount
			})
			doc = frappe.get_doc(args)
			doc.insert(ignore_permissions=True)
			doc.submit()

		def entry_Deposit_In_Transit():
			'''if(self.transaction_type=="Inter Branch"):
				args = _get_gl_structure(self)
				if(self.from_gl_entry and not self.to_gl_entry):
					args.update({
						'account': self.desposit_in_transit_account,
						'cost_center': self.from_cost_center,
						'against': self.desposit_in_transit_account,			
						'debit': self.total_amount,
						'debit_in_account_currency': self.total_amount,						
						'debit_in_transaction_currency': self.total_amount
					})'''

			if(self.transaction_type=="Inter Bank"):
				args = _get_gl_structure(self)
				if(self.from_gl_entry and not self.to_gl_entry):
					args.update({
						'account': self.desposit_in_transit_account,
						'cost_center': self.from_cost_center,
						'against': self.desposit_in_transit_account,			
						'debit': self.transfer_amount,
						'debit_in_account_currency': self.transfer_amount,						
						'debit_in_transaction_currency': self.transfer_amount
					})
				elif(self.to_gl_entry):
					args.update({
						'account': self.desposit_in_transit_account,
						'cost_center': self.from_cost_center,
						'against': self.desposit_in_transit_account,			
						'credit': self.transfer_amount,
						'credit_in_account_currency': self.transfer_amount,						
						'credit_in_transaction_currency': self.transfer_amount
					})
				
				doc = frappe.get_doc(args)	
				doc.insert(ignore_permissions=True)
				doc.submit()
		
		def entry_IBFT_Equity():
			if(self.transaction_type=="Inter Branch"):
				args = _get_gl_structure(self)
				if(self.from_gl_entry and not self.to_gl_entry):
					args.update({
						'account': self.ibft_equity_account,
						'cost_center': self.from_cost_center,
						'against': self.ibft_equity_account,
						'credit': self.total_amount,
						'credit_in_account_currency': self.total_amount,						
						'credit_in_transaction_currency': self.total_amount
					})

				elif(self.to_gl_entry):
					args.update({
						'account': self.ibft_equity_account,
						'cost_center': self.from_cost_center,
						'against': self.ibft_equity_account,			
						'debit': self.total_amount,
						'debit_in_account_currency': self.total_amount,						
						'debit_in_transaction_currency': self.total_amount
					})
				
				doc = frappe.get_doc(args)	
				doc.insert(ignore_permissions=True)
				doc.submit()

		# Start Execution
		validate_funds_transfer_to()
		
		if(self.from_gl_entry and not self.to_gl_entry): 
			gl_entries_funds_transfer_from()
			gl_entry_bank_from()
		# total_transfer_amount = gl_entries_funds_transfer_to()
		
		if(self.to_gl_entry): 
			gl_entries_funds_transfer_to()
			gl_entry_bank_to()

	def create_gl_entries_for_inter_funds_transfer(self):
		today_date = today()
		fiscal_year = get_fiscal_year(today_date, company=self.company)[0]
		if not self.funds_transfer_to:
			frappe.throw("There is no information to transfer funds.")
			return

		donor_list_data = self.donor_list_for_purchase_receipt()
		donor_list = donor_list_data['donor_list']
		total_transfer_amount = 0.0

		# Extract donor IDs from funds_transfer_from and funds_transfer_to
		donor_ids_from = {p.ff_donor for p in self.funds_transfer_from if p.ff_donor}
		donor_ids_to = {n.ft_donor for n in self.funds_transfer_to if n.ft_donor}

		# Check if any donor ID in funds_transfer_from is not in funds_transfer_to
		missing_donor_ids = donor_ids_from - donor_ids_to
		if missing_donor_ids:
			missing_donors_message = ", ".join(missing_donor_ids)
			# frappe.throw(f"No details are provided for Donor(s): {missing_donors_message}")
			frappe.throw("Donor must be Same")

		# Validate if there are exact matches between funds_transfer_from and funds_transfer_to
		for f in self.funds_transfer_from:
			for t in self.funds_transfer_to:
				# Check if all relevant fields match
				if (
					f.ff_company == t.ft_company and
					f.ff_cost_center == t.ft_cost_center and
					f.ff_service_area == t.ft_service_area and
					f.ff_subservice_area == t.ft_subservice_area and
					f.ff_product == t.ft_product and
					f.project == t.project and
					f.ff_account == t.ft_account and
					f.ff_donor == t.ft_donor
				):
					frappe.throw(f"Duplicate entry found: Funds Transfer From and Funds Transfer To have the same details for Donor {f.ff_donor}")

		# Accumulate total transfer amount and process donor entries
		for d in donor_list:
			prev_donor = d.get('donor')
			prev_cost_center = d.get('cost_center')
			prev_project = d.get('project')
			prev_program = d.get('service_area')
			prev_subservice_area = d.get('subservice_area')
			prev_product = d.get('product')
			prev_amount = float(d.get('balance', 0.0))
			prev_account = d.get('account')
			prev_company = d.get('company')

			for n in self.funds_transfer_to:
				new_donor = n.get('ft_donor')
				ftf_amount = float(n.get('ft_amount', 0.0))
				ftt_amount = float(n.get('ft_amount', 0.0))
				new_cost_center = n.get('ft_cost_center')
				new_account = n.get('ft_account')
				new_project = n.get('project')
				new_program = n.get('ft_service_area')
				new_subservice_area = n.get('ft_subservice_area')
				new_product = n.get('ft_product')
				new_company = n.get('ft_company')

				if prev_donor == new_donor:
					if prev_amount >= ftf_amount:  
						total_transfer_amount += ftf_amount

						# Debit entry for previous dimension; funds transfer from
						gl_entry_for_previous_dimension = frappe.get_doc({
							'doctype': 'GL Entry',
							'posting_date': self.posting_date,
							'transaction_date': self.posting_date,
							'account': prev_account,
							'against_voucher_type': 'Funds Transfer',
							'against_voucher': self.name,
							'cost_center': prev_cost_center,
							'debit': ftf_amount,
							'credit': 0.0,
							'account_currency': 'PKR',
							'debit_in_account_currency': ftf_amount,
							'credit_in_account_currency': 0.0,
							'against': prev_account,
							'voucher_type': 'Funds Transfer',
							'voucher_no': self.name,
							'remarks': 'Funds Transferred',
							'is_opening': 'No',
							'is_advance': 'No',
							'fiscal_year': fiscal_year,
							'company': prev_company,
							'transaction_currency': 'PKR',
							'debit_in_transaction_currency': ftf_amount,
							'credit_in_transaction_currency': 0.0,
							'transaction_exchange_rate': 1,
							'project': prev_project,
							'service_area': prev_program,
							'party_type': 'Donor',
							'party': prev_donor,
							'subservice_area': prev_subservice_area,
							'donor': prev_donor,
							'inventory_flag': 'Purchased',
							'product': prev_product
						})

						gl_entry_for_previous_dimension.insert(ignore_permissions=True)
						gl_entry_for_previous_dimension.submit()

						# Credit entry for new dimension; funds transfer from
						gl_entry_for_new_dimension = frappe.get_doc({
							'doctype': 'GL Entry',
							'posting_date': self.posting_date,
							'transaction_date': self.posting_date,
							'account': new_account,
							'against_voucher_type': 'Funds Transfer',
							'against_voucher': self.name,
							'cost_center': new_cost_center,
							'debit': 0.0,
							'credit': ftt_amount,
							'account_currency': 'PKR',
							'debit_in_account_currency': 0.0,
							'credit_in_account_currency': ftt_amount,
							'against': new_account,
							'voucher_type': 'Funds Transfer',
							'voucher_no': self.name,
							'remarks': 'Funds Transferred',
							'is_opening': 'No',
							'is_advance': 'No',
							'fiscal_year': fiscal_year,
							'company': new_company,
							'transaction_currency': 'PKR',
							'debit_in_transaction_currency': 0.0,
							'credit_in_transaction_currency': ftt_amount,
							'transaction_exchange_rate': 1,
							'project': new_project,
							'service_area': new_program,
							'party_type': 'Donor',
							'party': new_donor,
							'subservice_area': new_subservice_area,
							'donor': new_donor,
							'inventory_flag': 'Purchased',
							'product': new_product
						})

						gl_entry_for_new_dimension.insert(ignore_permissions=True)
						gl_entry_for_new_dimension.submit()

					else:
						frappe.throw(f"Not enough amount to transfer for Donor {new_donor}")

		# Create bank account GL entries only once after the loop
		if total_transfer_amount > 0:
			if self.from_bank:
				# Credit entry for bank account
				gl_entry_for_bank_credit = frappe.get_doc({
					'doctype': 'GL Entry',
					'posting_date': self.posting_date,
					'transaction_date': self.posting_date,
					'account': self.from_bank,
					'against_voucher_type': 'Funds Transfer',
					'against_voucher': self.name,
					'cost_center': self.from_cost_center,
					'debit': 0.0,
					'credit': total_transfer_amount,
					'account_currency': 'PKR',
					'debit_in_account_currency': 0.0,
					'credit_in_account_currency': total_transfer_amount,
					'against': self.from_bank,
					'voucher_type': 'Funds Transfer',
					'voucher_no': self.name,
					'remarks': 'Funds Transferred',
					'is_opening': 'No',
					'is_advance': 'No',
					'fiscal_year': fiscal_year,
					'company': new_company,
					'transaction_currency': 'PKR',
					'debit_in_transaction_currency': 0.0,
					'credit_in_transaction_currency': total_transfer_amount,
					'transaction_exchange_rate': 1,
				})

				gl_entry_for_bank_credit.insert(ignore_permissions=True)
				gl_entry_for_bank_credit.submit()

			if self.to_bank:
				# Debit entry for bank account
				gl_entry_for_bank_debit = frappe.get_doc({
					'doctype': 'GL Entry',
					'posting_date': self.posting_date,
					'transaction_date': self.posting_date,
					'account': self.to_bank,
					'against_voucher_type': 'Funds Transfer',
					'against_voucher': self.name,
					'cost_center': self.to_cost_center,
					'debit': total_transfer_amount,
					'credit': 0.0,
					'account_currency': 'PKR',
					'debit_in_account_currency': total_transfer_amount,
					'credit_in_account_currency': 0.0,
					'against': self.to_bank,
					'voucher_type': 'Funds Transfer',
					'voucher_no': self.name,
					'remarks': 'Funds Transferred',
					'is_opening': 'No',
					'is_advance': 'No',
					'fiscal_year': fiscal_year,
					'company': prev_company,
					'transaction_currency': 'PKR',
					'debit_in_transaction_currency': total_transfer_amount,
					'credit_in_transaction_currency': 0.0,
					'transaction_exchange_rate': 1,
				})

				gl_entry_for_bank_debit.insert(ignore_permissions=True)
				gl_entry_for_bank_debit.submit()

		frappe.msgprint("GL Entries Created Successfully")

		
	def create_gl_entries_for_inter_funds_transfer_previous(self):
		today_date = today()
		fiscal_year = get_fiscal_year(today_date, company=self.company)[0]
		if not self.funds_transfer_to:
			frappe.throw("There is no information to transfer funds.")
			return

		donor_list_data = self.donor_list_for_purchase_receipt()
		donor_list = donor_list_data['donor_list']
		total_transfer_amount = 0.0

		# Extract donor IDs from funds_transfer_from and funds_transfer_to
		donor_ids_from = {p.ff_donor for p in self.funds_transfer_from if p.ff_donor}
		donor_ids_to = {n.ft_donor for n in self.funds_transfer_to if n.ft_donor}

		# Check if any donor ID in funds_transfer_from is not in funds_transfer_to
		missing_donor_ids = donor_ids_from - donor_ids_to
		if missing_donor_ids:
			missing_donors_message = ", ".join(missing_donor_ids)
			frappe.throw(f"Donor must be Same: {missing_donors_message}")

		# Accumulate total transfer amount and process donor entries
		for d in donor_list:
			prev_donor = d.get('donor')
			prev_cost_center = d.get('cost_center')
			prev_project = d.get('project')
			prev_program = d.get('service_area')
			prev_subservice_area = d.get('subservice_area')
			prev_product = d.get('product')
			prev_amount = float(d.get('balance', 0.0))
			prev_account = d.get('account')
			prev_company = d.get('company')

			for n in self.funds_transfer_to:
				new_donor = n.get('ft_donor')
				ftf_amount = float(n.get('ft_amount', 0.0))  # Required amount to transfer
				# ftt_amount = float(n.get('outstanding_amount', 0.0))
				new_cost_center = n.get('ft_cost_center')
				new_account = n.get('ft_account')
				new_project = n.get('project')
				new_program = n.get('ft_service_area')
				new_subservice_area = n.get('ft_subservice_area')
				new_product = n.get('ft_product')
				new_company = n.get('ft_company')

				if prev_donor == new_donor:
					if prev_amount >= ftf_amount:  # Sufficient balance for this transfer
						# Accumulate total transfer amount
						total_transfer_amount += ftf_amount

						# Debit entry for previous dimension; funds transfer from
						gl_entry_for_previous_dimension = frappe.get_doc({
							'doctype': 'GL Entry',
							'posting_date': self.posting_date,
							'transaction_date': self.posting_date,
							'account': prev_account,
							'against_voucher_type': 'Funds Transfer',
							'against_voucher': self.name,
							'cost_center': prev_cost_center,
							'debit': ftf_amount,
							'credit': 0.0,
							'account_currency': 'PKR',
							'debit_in_account_currency': ftf_amount,
							'credit_in_account_currency': 0.0,
							'against': prev_account,
							'voucher_type': 'Funds Transfer',
							'voucher_no': self.name,
							'remarks': 'Funds Transferred',
							'is_opening': 'No',
							'is_advance': 'No',
							'fiscal_year': fiscal_year,
							'company': prev_company,
							'transaction_currency': 'PKR',
							'debit_in_transaction_currency': ftf_amount,
							'credit_in_transaction_currency': 0.0,
							'transaction_exchange_rate': 1,
							'project': prev_project,
							'service_area': prev_program,
							'party_type': 'Donor',
							'party': prev_donor,
							'subservice_area': prev_subservice_area,
							'donor': prev_donor,
							'inventory_flag': 'Purchased',
							'product': prev_product
						})

						gl_entry_for_previous_dimension.insert(ignore_permissions=True)
						gl_entry_for_previous_dimension.submit()

						# Credit entry for new dimension funds transfer to
						gl_entry_for_new_dimension = frappe.get_doc({
							'doctype': 'GL Entry',
							'posting_date': self.posting_date,
							'transaction_date': self.posting_date,
							'account': new_account,
							'against_voucher_type': 'Funds Transfer',
							'against_voucher': self.name,
							'cost_center': new_cost_center,
							'debit': 0.0,
							'credit': ftt_amount,
							'account_currency': 'PKR',
							'debit_in_account_currency': 0.0,
							'credit_in_account_currency': ftt_amount,
							'against': new_account,
							'voucher_type': 'Funds Transfer',
							'voucher_no': self.name,
							'remarks': 'Funds Transferred',
							'is_opening': 'No',
							'is_advance': 'No',
							'fiscal_year': fiscal_year,
							'company': new_company,
							'transaction_currency': 'PKR',
							'debit_in_transaction_currency': 0.0,
							'credit_in_transaction_currency': ftt_amount,
							'transaction_exchange_rate': 1,
							'project': new_project,
							'service_area': new_program,
							'party_type': 'Donor',
							'party': new_donor,
							'subservice_area': new_subservice_area,
							'donor': new_donor,
							'inventory_flag': 'Purchased',
							'product': new_product
						})

						gl_entry_for_new_dimension.insert(ignore_permissions=True)
						gl_entry_for_new_dimension.submit()

					else:
						frappe.throw(f"Not enough amount to transfer for Donor {new_donor}")

		# Create bank account GL entries only once after the loop
		if total_transfer_amount > 0:
			if self.from_bank:
				# Credit entry for bank account
				gl_entry_for_bank_credit = frappe.get_doc({
					'doctype': 'GL Entry',
					'posting_date': self.posting_date,
					'transaction_date': self.posting_date,
					'account': self.from_bank,
					'against_voucher_type': 'Funds Transfer',
					'against_voucher': self.name,
					'cost_center': self.from_cost_center,
					'debit': 0.0,
					'credit': total_transfer_amount,
					'account_currency': 'PKR',
					'debit_in_account_currency': 0.0,
					'credit_in_account_currency': total_transfer_amount,
					'against': total_transfer_amount,
					'voucher_type': 'Funds Transfer',
					'voucher_no': self.name,
					'remarks': 'Funds Transferred',
					'is_opening': 'No',
					'is_advance': 'No',
					'fiscal_year': fiscal_year,
					'company': new_company,
					'transaction_currency': 'PKR',
					'debit_in_transaction_currency': 0.0,
					'credit_in_transaction_currency': total_transfer_amount,
					'transaction_exchange_rate': 1,
				})

				gl_entry_for_bank_credit.insert(ignore_permissions=True)
				gl_entry_for_bank_credit.submit()

			if self.to_bank:
				# Debit entry for bank account
				gl_entry_for_bank_debit = frappe.get_doc({
					'doctype': 'GL Entry',
					'posting_date': self.posting_date,
					'transaction_date': self.posting_date,
					'account': self.to_bank,
					'against_voucher_type': 'Funds Transfer',
					'against_voucher': self.name,
					'cost_center': self.to_cost_center,
					'debit': total_transfer_amount,
					'credit': 0.0,
					'account_currency': 'PKR',
					'debit_in_account_currency': total_transfer_amount,
					'credit_in_account_currency': 0.0,
					'against': total_transfer_amount,
					'voucher_type': 'Funds Transfer',
					'voucher_no': self.name,
					'remarks': 'Funds Transferred',
					'is_opening': 'No',
					'is_advance': 'No',
					'fiscal_year': fiscal_year,
					'company': prev_company,
					'transaction_currency': 'PKR',
					'debit_in_transaction_currency': total_transfer_amount,
					'credit_in_transaction_currency': 0.0,
					'transaction_exchange_rate': 1,
				})

				gl_entry_for_bank_debit.insert(ignore_permissions=True)
				gl_entry_for_bank_debit.submit()

		frappe.msgprint("GL Entries Created Successfully")

	def donor_list_for_purchase_receipt(self):
		donor_list = []
		total_balance = 0
		unique_entries = set()
		docstatus = self.docstatus

		for p in self.funds_transfer_from:
			# Construct the condition
			condition_parts = []
			for field, value in [
				('subservice_area', p.ff_subservice_area),
				('donor', p.ff_donor),
				('project', p.project),
				('cost_center', p.ff_cost_center),
				('product', p.ff_product),
				('service_area', p.ff_service_area),
				('company', p.ff_company),
				('account', p.ff_account)
			]:
				if value in [None, 'None', '']:
					condition_parts.append(f"({field} IS NULL OR {field} = '')")
				else:
					condition_parts.append(f"{field} = '{value}'")

			condition = " AND ".join(condition_parts)

			# Print query for debugging
			# frappe.msgprint(f"Condition: {condition}")

			try:
				donor_entries = frappe.db.sql(f"""
					SELECT 
						SUM(credit - debit) AS total_balance,
						donor,
						service_area,
						subservice_area,
						project,
						cost_center,
						product,
						company,
						account
					FROM `tabGL Entry`
					WHERE 
						is_cancelled = 'No'
						{f'AND {condition}' if condition else ''}
					GROUP BY donor, service_area, subservice_area, project, cost_center, product, company, account
					HAVING total_balance >= 0
					ORDER BY total_balance DESC
				""", as_dict=True)
				# frappe.msgprint(f"Donor Entries: {donor_entries}")
			except Exception as e:
				frappe.throw(f"Error executing query: {e}")

			match_found = False

			for entry in donor_entries:
				if ((entry.get('service_area') == p.ff_service_area or (not entry.get('service_area') and not p.ff_service_area)) and
					(entry.get('subservice_area') == p.ff_subservice_area or (not entry.get('subservice_area') and not p.ff_subservice_area)) and
					(entry.get('project') == p.project or (not entry.get('project') and not p.project)) and
					(entry.get('cost_center') == p.ff_cost_center or (not entry.get('cost_center') and not p.ff_cost_center)) and
					(entry.get('product') == p.ff_product or (not entry.get('product') and not p.ff_product)) and
					(entry.get('account') == p.ff_account or (not entry.get('account') and not p.ff_account)) and
					(entry.get('company') == p.ff_company or (not entry.get('company') and not p.ff_company))):

					entry_key = (
						entry.get('donor'), 
						entry.get('service_area'), 
						entry.get('subservice_area'), 
						entry.get('project'),
						entry.get('cost_center'),
						entry.get('product'),
						entry.get('company'),
						entry.get('account'),
					)

					if entry_key not in unique_entries:
						unique_entries.add(entry_key)
						balance = entry['total_balance']
							
						used_amount = 0

						if docstatus == 1:
							try:
								used_amount_data = frappe.db.sql(f"""
									SELECT SUM(debit) as used_amount
									FROM `tabGL Entry`
									WHERE 
										
										voucher_no = '{self.name}'
										{f'AND {condition}' if condition else ''}
								""", as_dict=True)
								if used_amount_data:
									used_amount = used_amount_data[0].get('used_amount', 0)
							except Exception as e:
								frappe.throw(f"Error fetching used amount: {e}")

						donor_list.append({
							"donor": p.ff_donor,
							"service_area": p.ff_service_area,
							"subservice_area": p.ff_subservice_area,
							"project": p.project,
							"cost_center": p.ff_cost_center,
							"product": p.ff_product,
							"company": p.ff_company,
							"account": p.ff_account,
							"balance": balance,
							"used_amount": used_amount,
						})
						# frappe.msgprint(f"donor_list: {donor_list}")
						

						total_balance += balance
						match_found = True
						break

			if not match_found:
				if p.ff_donor:
					frappe.msgprint(f'No such entry exists for donor "<bold>{p.ff_donor}</bold>" with provided details.')
				else: 
					frappe.msgprint(f'No such entry exists against Cost Center "<bold>{p.ff_cost_center,}</bold>" and Bank Account {p.ff_account}.')

		# if donor_list:
		#     frappe.msgprint('GL Entries Created Successfully')

		return {
			"total_balance": total_balance,
			"donor_list": donor_list  
		}

	def get_new_dimensions(self, donor_list):
		result = []
		fields = []
		docstatus = self.docstatus
		for n in self.funds_transfer_to:
			for p in donor_list:
				# if (n.ft_donor == p.get('donor') or n.ft_cost_center == p.get('cost_center') or
				#     n.ft_service_area == p.get('program') or n.ft_subservice_area == p.get('subservice_area')):
					fields.append({
						'donor': n.ft_donor,
						'cost_center': n.ft_cost_center,
						'project': n.project,
						'service_area': n.ft_service_area,
						'subservice_area': n.ft_subservice_area,
						'product': n.ft_product,
						'amount': n.outstanding_amount,
						'account': n.ft_account,
						'company': n.ft_company
					})
			if fields:
				result.append({
					'fields': fields
				})
		return result

@frappe.whitelist()
def donor_list_data_funds_transfer(doc):
    try:
        doc = frappe.get_doc(json.loads(doc))
    except (json.JSONDecodeError, TypeError) as e:
        frappe.throw(f"Invalid input: {e}")

    donor_list = []
    total_balance = 0
    unique_entries = set()
    duplicate_entries = set()
    insufficient_balances = set()
    no_entries_found = set()
    docstatus = doc.docstatus
    
    
    def validate_missing_info(funds_from_row):
        # frappe.throw(frappe.as_json(funds_from_row))
        conditions = ""
        for field1, field2 in [
            ('gl.subservice_area', "ff_subservice_area"),
            ('gl.donor', "ff_donor"),
            ('gl.project', "project"),
            ('gl.cost_center', "ff_cost_center"),
            ('gl.product', "ff_product"),
            ('gl.service_area', "ff_service_area"),
            ('gl.company', "ff_company"),
            ('gl.account', "ff_account")]:
            value2 = funds_from_row.get(field2)
            if(value2):
                conditions += f" and {field1} = '{value2}' "
            else:
                label =  field2.replace("ff_", "")
                label =  label.replace("_", " ")
                frappe.throw(f"Row#{funds_from_row.idx}, please select <b>{label.capitalize()}</b>", title="Funds Transfer From")
        return conditions
    
    def get_donor_list(condition):
        """ sql by nabeel saleem """
        query = f"""  Select 
                ifnull((sum(distinct gl.credit) - sum(distinct gl.debit)),0) as total_balance,
                gl.donor,
                (select donor_name from `tabDonor` where name=gl.donor) as donor_name,
                gl.service_area,
                gl.subservice_area,
                gl.project,
                gl.cost_center,
                gl.product,
                gl.company,
                gl.account
            From 
                `tabGL Entry` gl, `tabDonation` d, `tabFunds Transfer` ft
            Where 
                (gl.voucher_no = d.name or gl.voucher_no = ft.name)
                and d.contribution_type ='Donation'
                and gl.is_cancelled=0
                and voucher_type  in ('Donation', 'Funds Transfer')
                and gl.account in (select name from `tabAccount` where disabled=0 and account_type='Equity' and name=gl.account)
                {f'{condition}' if condition else ''}
            Having 
                total_balance>0
            Order By 
                total_balance desc
            """
        return frappe.db.sql(query, as_dict=True)
            
    for p in doc.funds_transfer_from:
        # Construct the condition
        condition = validate_missing_info(p)
        try:
            donor_entries = get_donor_list(condition)
            # frappe.msgprint(f"donor_entries: {donor_entries}")
        except Exception as e:
            frappe.throw(f"Error executing query: {e}")
        match_found = False

        for entry in donor_entries:
            entry_key = (
                entry.get('donor'), 
                entry.get('service_area'), 
                entry.get('subservice_area'), 
                entry.get('project'),
                entry.get('cost_center'),
                entry.get('product'),
                entry.get('company'),
                entry.get('account'),
            )

            if entry_key in unique_entries:
                # Mark it as a duplicate and notify the user
                if entry_key not in duplicate_entries:
                    duplicate_entries.add(entry_key)
                    frappe.msgprint(f'<span style="color: red;">Row#{p.idx}; duplicate entry exists for donor "{entry.get("donor")}" with provided details.</span>')
            else:
                # Add to unique entries if not seen before
                unique_entries.add(entry_key)
                balance = entry.total_balance
                used_amount = 0

                # Handle balance checks
                if balance <= 0.0 and not doc.is_new() and docstatus == 0:
                    # Exclude negative balances and track insufficient balance
                    if balance < 0:
                        insufficient_balances.add(entry.get('donor'))
                    else:
                        if p.ff_donor:
                            insufficient_balances.add(p.ff_donor)
                        else: 
                            insufficient_balances.add(f"Cost Center '{p.ff_cost_center}' and Bank Account {p.ff_account}")
                    match_found = True
                    break

                # Fetch used amount if needed
                if docstatus == 1:
                    try:
                        used_amount_query = f"""
                            SELECT SUM(debit) as used_amount
                            FROM `tabGL Entry`
                            WHERE 
                                voucher_no = '{doc.name}'
                                {f'AND {condition}' if condition else ''}
                        """
                        used_amount_data = frappe.db.sql(used_amount_query, as_dict=True)
                        if used_amount_data:
                            used_amount = used_amount_data[0].get('used_amount', 0)
                    except Exception as e:
                        frappe.throw(f"Error fetching used amount: {e}")

                # Append donor data to the donor list
                donor_list.append({
                    "donor": p.ff_donor,
                    "donor_name": p.ff_donor_name or "-",
                    "service_area": p.ff_service_area,
                    "subservice_area": p.ff_subservice_area,
                    "project": p.project,
                    "cost_center": p.ff_cost_center,
                    "product": p.ff_product,
                    "company": p.ff_company,
                    "account": p.ff_account,
                    "balance": fmt_money(balance, currency="PKR"),
                    "used_amount": fmt_money(used_amount, currency="PKR"),
                })
                total_balance += balance
                match_found = True
    
        # Only add to no_entries_found if not a duplicate entry
        if not match_found and p.ff_donor not in [entry[0] for entry in duplicate_entries]:
            if p.ff_donor:
                no_entries_found.add(p.ff_donor)
            else: 
                no_entries_found.add(f"Cost Center '{p.ff_cost_center}' and Bank Account {p.ff_account}")

    # Display insufficient balance messages for tracked donors
    if docstatus == 0 :
        for donor in insufficient_balances:
            if donor not in [entry[0] for entry in duplicate_entries]:
                if donor:
                    frappe.msgprint(f'<span style="color: red;">Insufficient balance for donor "{donor}" with provided details.</span>')
                

        # Display no entries found messages
        for item in no_entries_found:
            frappe.msgprint(f'<span style="color: red;">No balance exists for <b>{item}</b> with provided details.</span>', title="Funds Transfer From")

    return {
        "total_balance": fmt_money(total_balance, currency="PKR"),
        "donor_list": donor_list  
    }

@frappe.whitelist()
def donor_list_data_funds_transfer_previous(doc):
    try:
        doc = frappe.get_doc(json.loads(doc))
    except (json.JSONDecodeError, TypeError) as e:
        frappe.throw(f"Invalid input: {e}")

    donor_list = []
    total_balance = 0
    unique_entries = set()
    docstatus = doc.docstatus

    for p in doc.funds_transfer_from:
        # Construct the condition
        condition_parts = []
        for field, value in [
            ('subservice_area', p.ff_subservice_area),
            ('donor', p.ff_donor),
            ('project', p.project),
            ('cost_center', p.ff_cost_center),
            ('product', p.ff_product),
            ('service_area', p.ff_service_area),
            ('company', p.ff_company),
            ('account', p.ff_account)
        ]:
            if value in [None, 'None', '']:
                condition_parts.append(f"({field} IS NULL OR {field} = '')")
            else:
                condition_parts.append(f"{field} = '{value}'")

        condition = " AND ".join(condition_parts)
        # frappe.msgprint(f"Condition: {condition}")

        query = f"""
            SELECT 
                SUM(credit - debit) AS total_balance,
                donor,
                service_area,
                subservice_area,
                project,
                cost_center,
                product,
                company,
                account
            FROM `tabGL Entry`
            WHERE 
                is_cancelled = 'No'
                {f'AND {condition}' if condition else ''}
               
            GROUP BY donor, service_area, subservice_area, project, cost_center, product, company, account
           
            ORDER BY total_balance DESC
        """
        # frappe.msgprint(f"Executing query: {query}")

        try:
            donor_entries = frappe.db.sql(query, as_dict=True)
            # frappe.msgprint(f"donor_entries: {donor_entries}")
        except Exception as e:
            frappe.throw(f"Error executing query: {e}")

        match_found = False

        for entry in donor_entries:
            if ((entry.get('service_area') == p.ff_service_area or (not entry.get('service_area') and not p.ff_service_area)) and
                (entry.get('subservice_area') == p.ff_subservice_area or (not entry.get('subservice_area') and not p.ff_subservice_area)) and
                (entry.get('project') == p.project or (not entry.get('project') and not p.project)) and
                (entry.get('cost_center') == p.ff_cost_center or (not entry.get('cost_center') and not p.ff_cost_center)) and
                (entry.get('product') == p.ff_product or (not entry.get('product') and not p.ff_product)) and
                (entry.get('account') == p.ff_account or (not entry.get('account') and not p.ff_account)) and
                (entry.get('company') == p.ff_company or (not entry.get('company') and not p.ff_company))):
                
                entry_key = (
                    entry.get('donor'), 
                    entry.get('service_area'), 
                    entry.get('subservice_area'), 
                    entry.get('project'),
                    entry.get('cost_center'),
                    entry.get('product'),
                    entry.get('company'),
                    entry.get('account'),
                )

                if entry_key not in unique_entries:
                    unique_entries.add(entry_key)
                    balance = entry['total_balance']
                    used_amount = 0

                    # Check if the balance is 0
                    if balance == 0.0 and not doc.is_new() and docstatus == 0:
                    # if balance <= 0:
                        if p.ff_donor:
                            frappe.msgprint(f"Insufficient balance for donor '{p.ff_donor}' with provided details.")
                        else: 
                            frappe.msgprint(f"Insufficient balance against Cost Center '{p.ff_cost_center}' and Bank Account {p.ff_account}")
                        match_found = True
                        break

                    if docstatus == 1:
                        try:
                            used_amount_query = f"""
                                SELECT SUM(debit) as used_amount
                                FROM `tabGL Entry`
                                WHERE 
                                    voucher_no = '{doc.name}'
                                    {f'AND {condition}' if condition else ''}
                            """
                            # frappe.msgprint(f"Executing used_amount_query: {used_amount_query}")
                            used_amount_data = frappe.db.sql(used_amount_query, as_dict=True)
                            if used_amount_data:
                                used_amount = used_amount_data[0].get('used_amount', 0)
                        except Exception as e:
                            frappe.throw(f"Error fetching used amount: {e}")

                    donor_list.append({
                        "donor": p.ff_donor,
                        "service_area": p.ff_service_area,
                        "subservice_area": p.ff_subservice_area,
                        "project": p.project,
                        "cost_center": p.ff_cost_center,
                        "product": p.ff_product,
                        "company": p.ff_company,
                        "account": p.ff_account,
                        "balance": balance,
                        "used_amount": used_amount,
                    })
                    # frappe.msgprint(f"Donor List: {donor_list}")
                    total_balance += balance
                    match_found = True
                    break


        if not match_found:
            if p.ff_donor:
                frappe.msgprint(f'No such entry exists for donor "<bold>{p.ff_donor}</bold>" with provided details.')
            else: 
                frappe.msgprint(f'No such entry exists against Cost Center "<bold>{p.ff_cost_center,}</bold>" and Bank Account {p.ff_account}with provided details.')
    if donor_list:
        pass
        # frappe.msgprint('GL Entries Created Successfully')

    return {
        "total_balance": total_balance,
        "donor_list": donor_list  
    }

@frappe.whitelist()
def get_service_areas(doc):
    try:
        doc = frappe.get_doc(json.loads(doc))
    except (json.JSONDecodeError, TypeError) as e:
        frappe.throw(f"Invalid input: {e}")
    # frappe.msgprint(frappe.as_json(doc))

    company = []
    for f in doc.funds_transfer_from:
        company.append(f.ff_company)
    # frappe.msgprint(frappe.as_json(company))
    return company


def _get_gl_structure(self):
	fiscal_year = get_fiscal_year(today(), company=self.company)[0]
	return {
		'doctype': 'GL Entry',
		'posting_date': self.posting_date,
		'transaction_date': self.posting_date,
		'party_type': '',
		'party': '',
		'voucher_type': 'Funds Transfer',
		'voucher_no': self.name,
		'against_voucher_type': 'Funds Transfer',
		'against_voucher': self.name,
		'remarks': 'Funds Transferred',
		'is_opening': 'No',
		'is_advance': 'No',
		'fiscal_year': fiscal_year,
		'company': self.company,
		'account_currency': 'PKR',
		'transaction_currency': 'PKR',
		'transaction_exchange_rate': 1,
		'project': '',
		'service_area': '',
		'subservice_area': '',
		'product': '',     
		'donor': '',
		'inventory_flag': '',
		# not common arguments
		'cost_center': '',
		'account': '',
		'against': '',
		'debit': 0.0,
		'credit': 0.0,
		'debit_in_account_currency': 0.0,
		'credit_in_account_currency': 0.0,
		'debit_in_transaction_currency': 0.0,
		'credit_in_transaction_currency': 0.0
	}

