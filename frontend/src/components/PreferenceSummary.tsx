import type { UserPreference } from '../api';


const INTENSITY_LABELS: Record<UserPreference['activity_intensity'], string> = {
  light: '轻松',
  medium: '适中',
  high: '高强度',
};


export function formatPreferenceSummary(preference: UserPreference): string {
  const parts = [
    INTENSITY_LABELS[preference.activity_intensity],
    `${preference.max_travel_minutes} 分钟内`,
    preference.dining_preferences[0],
  ].filter((value): value is string => Boolean(value));
  if (preference.prefer_indoor) parts.push('室内优先');
  if (preference.prefer_low_wait) parts.push('少排队');
  return parts.join(' · ');
}


export default function PreferenceSummary({
  preference,
}: {
  preference: UserPreference | null;
}) {
  return (
    <p className="text-sm leading-6 text-slate-500">
      <span className="font-semibold text-slate-700">当前偏好：</span>
      {preference ? formatPreferenceSummary(preference) : '正在读取...'}
    </p>
  );
}
