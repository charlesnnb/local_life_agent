import { useEffect, useState } from 'react';

import {
  getCurrentPreferences,
  getDefaultPreferences,
  PreferenceSetupData,
  savePreferences,
  UserPreference,
} from '../api';


const INTENSITY_LABELS = {
  light: '轻松',
  medium: '中等',
  high: '高强度',
};

const BUDGET_LABELS = {
  low: '低预算',
  medium: '中等预算',
  high: '高预算',
};


function PreferenceSetup() {
  const [setup, setSetup] = useState<PreferenceSetupData | null>(null);
  const [preference, setPreference] = useState<UserPreference | null>(null);
  const [savedSummary, setSavedSummary] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([getDefaultPreferences(), getCurrentPreferences()])
      .then(([defaultSetup, current]) => {
        setSetup(defaultSetup);
        setPreference(current.preference);
        setSavedSummary(formatSummary(current.preference));
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : '偏好加载失败');
      });
  }, []);

  const toggleListValue = (
    field: 'activity_types' | 'dining_preferences',
    value: string,
  ) => {
    setPreference(current => {
      if (!current) return current;
      const values = current[field];
      return {
        ...current,
        [field]: values.includes(value)
          ? values.filter(item => item !== value)
          : [...values, value],
      };
    });
    setSavedSummary('');
  };

  const save = async () => {
    if (!preference) return;
    setSaving(true);
    setError('');
    try {
      const profile = await savePreferences(preference);
      setPreference(profile.preference);
      setSavedSummary(formatSummary(profile.preference));
    } catch (err) {
      setError(err instanceof Error ? err.message : '偏好保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (!setup || !preference) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-slate-500">
          {error || '正在加载个性化偏好...'}
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-600">
          Preference Profile
        </p>
        <h2 className="mt-1 text-lg font-bold">先告诉 Agent 你通常喜欢什么</h2>
        <p className="mt-1 text-sm text-slate-500">
          当前 Demo 只保存在内存中，会影响后续活动和餐厅排序。
        </p>
      </div>

      <PreferenceGroup title="更喜欢哪些活动？">
        <OptionButtons
          options={setup.options.activity_types}
          selected={preference.activity_types}
          onToggle={value => toggleListValue('activity_types', value)}
        />
      </PreferenceGroup>

      <PreferenceGroup title="可接受的单程通勤时间？">
        <div className="flex flex-wrap gap-2">
          {setup.options.max_travel_minutes.map(minutes => (
            <button
              key={minutes}
              type="button"
              onClick={() => {
                setPreference(current => current && {
                  ...current,
                  max_travel_minutes: minutes as 15 | 30 | 45,
                });
                setSavedSummary('');
              }}
              className={optionClass(
                preference.max_travel_minutes === minutes,
              )}
            >
              {minutes} 分钟内
            </button>
          ))}
        </div>
      </PreferenceGroup>

      <PreferenceGroup title="餐饮偏好？">
        <OptionButtons
          options={setup.options.dining_preferences}
          selected={preference.dining_preferences}
          onToggle={value => toggleListValue('dining_preferences', value)}
        />
      </PreferenceGroup>

      <div className="mt-5 grid gap-5 sm:grid-cols-2">
        <label className="text-sm font-semibold text-slate-700">
          活动强度
          <select
            value={preference.activity_intensity}
            onChange={event => {
              setPreference(current => current && {
                ...current,
                activity_intensity: event.target.value as UserPreference['activity_intensity'],
              });
              setSavedSummary('');
            }}
            className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-violet-500"
          >
            {setup.options.activity_intensity.map(value => (
              <option key={value} value={value}>
                {INTENSITY_LABELS[value as keyof typeof INTENSITY_LABELS]}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm font-semibold text-slate-700">
          预算偏好
          <select
            value={preference.budget_level}
            onChange={event => {
              setPreference(current => current && {
                ...current,
                budget_level: event.target.value as UserPreference['budget_level'],
              });
              setSavedSummary('');
            }}
            className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-violet-500"
          >
            {setup.options.budget_level.map(value => (
              <option key={value} value={value}>
                {BUDGET_LABELS[value as keyof typeof BUDGET_LABELS]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-5 flex flex-wrap gap-4">
        <PreferenceToggle
          label="优先室内"
          checked={preference.prefer_indoor}
          onChange={checked => {
            setPreference(current => current && {
              ...current,
              prefer_indoor: checked,
            });
            setSavedSummary('');
          }}
        />
        <PreferenceToggle
          label="尽量少排队"
          checked={preference.prefer_low_wait}
          onChange={checked => {
            setPreference(current => current && {
              ...current,
              prefer_low_wait: checked,
            });
            setSavedSummary('');
          }}
        />
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-violet-700 disabled:opacity-50"
        >
          {saving ? '正在保存...' : '保存偏好'}
        </button>
        {savedSummary && (
          <p className="text-sm text-emerald-700">
            已保存偏好：{savedSummary}
          </p>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </section>
  );
}


function PreferenceGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-5">
      <p className="mb-2 text-sm font-semibold text-slate-700">{title}</p>
      {children}
    </div>
  );
}


function OptionButtons({
  options,
  selected,
  onToggle,
}: {
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(option => (
        <button
          key={option}
          type="button"
          onClick={() => onToggle(option)}
          className={optionClass(selected.includes(option))}
        >
          {option}
        </button>
      ))}
    </div>
  );
}


function PreferenceToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={event => onChange(event.target.checked)}
        className="h-4 w-4 accent-violet-600"
      />
      {label}
    </label>
  );
}


function optionClass(selected: boolean) {
  return [
    'rounded-full border px-3 py-1.5 text-sm transition',
    selected
      ? 'border-violet-500 bg-violet-50 font-medium text-violet-700'
      : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300',
  ].join(' ');
}


function formatSummary(preference: UserPreference) {
  const parts = [
    ...preference.activity_types.slice(0, 2),
    ...preference.dining_preferences.slice(0, 2),
    `${preference.max_travel_minutes}分钟内`,
  ];
  if (preference.prefer_indoor) parts.push('室内优先');
  if (preference.prefer_low_wait) parts.push('少排队');
  return parts.join(' / ');
}


export default PreferenceSetup;
