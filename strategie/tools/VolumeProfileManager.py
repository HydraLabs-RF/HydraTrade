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
        # Normalize timezone safety
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        target_date = current_time.date()

        # --- SESSION 1: TODAY ---
        # Start: today at 00:00:00
        start_today = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        # End: either NOW (current_time) or, if current_time is exactly midnight, end of day
        if current_time.hour == 0 and current_time.minute == 0 and current_time.second == 0:
            end_today = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        else:
            end_today = current_time

        current_profile = SessionProfile(self.bin_size)
        current_profile.build_for_specific_day(start_time=start_today, end_time=end_today)


        # --- SESSION 2: LAST TRADING DAY (not strictly calendar previous day) ---
        # Calendar previous day may be Sunday/holiday -> empty profile -> strategy
        # would get no valid prior-day profile (e.g. Monday). So walk backward
        # until the last day with a real profile. Past only -> no lookahead.
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
