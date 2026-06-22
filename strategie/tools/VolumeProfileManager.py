from datetime import datetime, date, timedelta, timezone
from typing import Tuple, Optional
from strategie.tools.helpFunctions.volumeSessionProfile import SessionProfile

class DailyVolumeProfileManager:
    def __init__(self, bin_size: float):
        self.bin_size = bin_size

    def get_profiles(self, current_time: datetime) -> Tuple[Optional[SessionProfile], Optional[SessionProfile]]:
        # Zeitzonen-Sicherheit flachbügeln
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        target_date = current_time.date()

        # --- SESSION 1: HEUTE ---
        # Start: Heute um 00:00:00 Uhr
        start_today = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        # Ende: Entweder JETZT (current_time) oder, falls current_time exakt Mitternacht ist, das Ende des Tages
        if current_time.hour == 0 and current_time.minute == 0 and current_time.second == 0:
            end_today = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        else:
            end_today = current_time

        current_profile = SessionProfile(self.bin_size)
        current_profile.build_for_specific_day(start_time=start_today, end_time=end_today)


        # --- SESSION 2: GESTERN ---
        # Exakt von Gestern 00:00:00 Uhr bis Gestern 23:59:59 Uhr
        yesterday = target_date - timedelta(days=1)
        start_yesterday = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_yesterday = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=timezone.utc)

        prior_profile = SessionProfile(self.bin_size)
        prior_profile.build_for_specific_day(start_time=start_yesterday, end_time=end_yesterday)

        return current_profile, prior_profile