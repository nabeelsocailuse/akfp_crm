# Copyright (c) 2025, Al-Khidmat Foundation and contributors
# For license information, please see license.txt

import os
from pathlib import Path
from werkzeug.wrappers import Response

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer


class VerificationPageRenderer(BaseRenderer):
	__slots__ = ("path", "file_path")
	
	def __init__(self, path, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		self.set_file_path()
	
	def set_file_path(self):
		self.file_path = ""
		app_path = frappe.get_app_path("akfp_crm", "public", "www", "verify-certificate.html")
		if os.path.isfile(app_path):
			self.file_path = app_path
	
	def can_render(self):
		# Handle both with and without .html extension
		return self.file_path and (
			self.path == "akfp_crm/www/verify-certificate.html" or 
			self.path == "verify-certificate" or
			self.path == "akfp_crm/www/verify-certificate"
		)
	
	def render(self):
		with open(self.file_path, 'r', encoding='utf-8') as f:
			html_content = f.read()
		
		return Response(
			html_content,
			mimetype='text/html'
		)

