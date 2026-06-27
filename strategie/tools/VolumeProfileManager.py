from datetime import datetime, date, timedelta, timezone
from typing import Tuple, Optional
from strategie.tools.helpFunctions.volumeSessionProfile import SessionProfile

class DailyVolumeProfileManager:
    # How far back to look for the last day that actually traded (skips
    # weekends/holidays). A long holiday weekend rarely exceeds a few days.
    MAX_PRIOR_LOOKBACK_DAYS = 7

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


        # --- SESSION 2: LETZTER HANDELSTAG (nicht stur Kalender-Vortag) ---
        # Der Kalender-Vortag kann Sonntag/Feiertag sein -> leeres Profil -> Strategie
        # bekäme kein gültiges Vortags-Profil (z.B. Montag). Daher rückwärts laufen
        # bis zum letzten Tag mit echtem Profil. Nur Vergangenheit -> kein Lookahead.
        prior_profile = SessionProfile(self.bin_size)
        probe = target_date - timedelta(days=1)
        for _ in range(self.MAX_PRIOR_LOOKBACK_DAYS):
            start_p = datetime.combine(probe, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_p = datetime.combine(probe, datetime.max.time()).replace(tzinfo=timezone.utc)
            candidate = SessionProfile(self.bin_size)
            candidate.build_for_specific_day(start_time=start_p, end_time=end_p)
            if candidate.profile:
                prior_profile = candidate
                break
            probe -= timedelta(days=1)

        return current_profile, prior_profile
