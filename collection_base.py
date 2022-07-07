import calendar
from enum import Enum
from datetime import datetime


class CollectionType(Enum):
    LEGACY_CAS = 0
    GBIF_BERKELEY = 1
    GBIF_CAS = 2


class CollectionBase:
    def __init__(self, title, type):
        self.downloads_by_month = {}
        self.unique_users_by_years = {}
        self.title = title
        self.collction_type = type

    def _setup_downloads_by_years(self, date_time_obj):
        if date_time_obj.year not in self.downloads_by_month:
            self.downloads_by_month[date_time_obj.year] = {}
        if date_time_obj.month not in self.downloads_by_month[date_time_obj.year]:
            self.downloads_by_month[date_time_obj.year][date_time_obj.month] = []

    def _append_values(self, source_dict, func):
        year_keys = sorted(list(source_dict.keys()))
        indices=[]
        values=[]
        today = datetime.today()
        current_month = today.month
        current_year = today.year
        first_month = None
        for year in year_keys:
            month_keys = range(1,13)
            for month in month_keys:
                if month in source_dict[year]:
                    first_month = month
                    values.append(func(source_dict[year][month]))
                    indices.append(f"{calendar.month_name[month]} {year}")
                else:
                    if first_month is not None and not (current_year == year and month > current_month ):
                        values.append(0)
                        indices.append(f"{calendar.month_name[month]} {year}")

        return indices,values


    def get_downloads_array(self):
        return self._append_values(self.downloads_by_month, len)


    def get_unique_users_array(self):

        return(self._append_values(self.unique_users_by_years, int))

