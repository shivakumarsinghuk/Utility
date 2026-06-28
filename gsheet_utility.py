# Importing required library
import pygsheets

class gsheet_utility:
    def __init__(self, account_file, spread_sheet_name):
        print("account file: ", account_file)
        self.client = pygsheets.authorize(service_account_file=account_file)
        self.spread_sheet = self.client.open(spread_sheet_name)

    def get_work_sheet(self, p_work_sheet):
        l_spread_sheet = None
        try:
            l_spread_sheet = self.spread_sheet.worksheet("title", p_work_sheet)
        except:
            print("Excpetion while getting work sheet")
        return l_spread_sheet
    
    def get_last_row(self, p_spread_sheet:pygsheets.worksheet.Worksheet, p_range='A1'):
        l_last_row = 0
        try:
            print(p_spread_sheet.get_values_batch(p_range)[0])
            l_last_row = len(p_spread_sheet.get_values_batch(p_range)[0])
        except:
            print("Excpetion while getting last row")
        return l_last_row
