import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  getCurrentPreferences,
  getDefaultPreferences,
  PreferenceSetupData,
  savePreferences,
  UserPreference,
} from '../api';


const STEP_TITLES = [
  '你更喜欢什么活动？',
  '你能接受多远的通勤？',
  '你的餐饮偏好是什么？',
  '预算和节奏',
] as const;

const INTENSITY_LABELS: Record<UserPreference['activity_intensity'], string> = {
  light: '轻松',
  medium: '适中',
  high: '高强度',
};

const BUDGET_LABELS: Record<UserPreference['budget_level'], string> = {
  low: '低预算',
  medium: '中等预算',
  high: '高预算',
};


export default function PreferencesPage() {
  const navigate = useNavigate();
  const [setup, setSetup] = useState<PreferenceSetupData | null>(null);
  const [preference, setPreference] = useState<UserPreference | null>(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const navigateTimer = useRef<number | null>(null);

  useEffect(() => {
    Promise.all([getDefaultPreferences(), getCurrentPreferences()])
      .then(([defaultSetup, current]) => {
        setSetup(defaultSetup);
        setPreference(current.preference);
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : '偏好加载失败');
      });
    return () => {
      if (navigateTimer.current !== null) {
        window.clearTimeout(navigateTimer.current);
      }
    };
  }, []);

  const toggleList = (
    field: 'activity_types' | 'dining_preferences',
    value: string,
  ) => {
    setPreference(current => {
      if (!current) return current;
      return {
        ...current,
        [field]: current[field].includes(value)
          ? current[field].filter(item => item !== value)
          : [...current[field], value],
      };
    });
  };

  const save = async () => {
    if (!preference) return;
    setSaving(true);
    setError('');
    try {
      await savePreferences(preference);
      localStorage.setItem('preference-questionnaire-completed', 'true');
      sessionStorage.removeItem('preference-prompt-dismissed');
      setSaved(true);
      navigateTimer.current = window.setTimeout(() => {
        navigate('/', { replace: true });
      }, 350);
    } catch (err) {
      setError(err instanceof Error ? err.message : '偏好保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (!setup || !preference) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <p className="text-sm text-slate-500">
            {error || '正在加载偏好问卷...'}
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-6 sm:px-8">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">
            Preference setup
          </p>
          <h1 className="mt-2 text-2xl font-bold text-slate-950 sm:text-3xl">
            用 1 分钟，让推荐更懂你
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            偏好继续保存在后端内存 profile 中，只用浏览器记录问卷是否完成。
          </p>
        </div>

        <div className="px-5 py-6 sm:px-8 sm:py-8">
          <div className="flex items-center justify-between gap-4">
            <p className="text-sm font-bold text-blue-700">
              步骤 {step + 1} / 4
            </p>
            <div className="flex gap-1.5" aria-label="问卷进度">
              {STEP_TITLES.map((_, index) => (
                <span
                  key={index}
                  className={`h-1.5 w-8 rounded-full ${
                    index <= step ? 'bg-blue-600' : 'bg-slate-200'
                  }`}
                />
              ))}
            </div>
          </div>

          <h2 className="mt-5 text-xl font-bold text-slate-950">
            {STEP_TITLES[step]}
          </h2>

          <div className="mt-5 min-h-56">
            {step === 0 && (
              <ChoiceGrid
                options={setup.options.activity_types}
                selected={preference.activity_types}
                onSelect={value => toggleList('activity_types', value)}
              />
            )}
            {step === 1 && (
              <ChoiceGrid
                options={setup.options.max_travel_minutes.map(
                  minutes => `${minutes} 分钟内`,
                )}
                selected={[`${preference.max_travel_minutes} 分钟内`]}
                onSelect={value => setPreference(current => current && ({
                  ...current,
                  max_travel_minutes: Number.parseInt(value, 10) as 15 | 30 | 45,
                }))}
                single
              />
            )}
            {step === 2 && (
              <ChoiceGrid
                options={setup.options.dining_preferences}
                selected={preference.dining_preferences}
                onSelect={value => toggleList('dining_preferences', value)}
              />
            )}
            {step === 3 && (
              <div className="space-y-6">
                <QuestionBlock title="活动强度">
                  <ChoiceGrid
                    options={setup.options.activity_intensity.map(
                      value => INTENSITY_LABELS[
                        value as UserPreference['activity_intensity']
                      ],
                    )}
                    selected={[INTENSITY_LABELS[preference.activity_intensity]]}
                    onSelect={label => {
                      const value = Object.entries(INTENSITY_LABELS).find(
                        ([, itemLabel]) => itemLabel === label,
                      )?.[0] as UserPreference['activity_intensity'];
                      setPreference(current => current && ({
                        ...current,
                        activity_intensity: value,
                      }));
                    }}
                    single
                  />
                </QuestionBlock>
                <QuestionBlock title="预算">
                  <ChoiceGrid
                    options={setup.options.budget_level.map(
                      value => BUDGET_LABELS[
                        value as UserPreference['budget_level']
                      ],
                    )}
                    selected={[BUDGET_LABELS[preference.budget_level]]}
                    onSelect={label => {
                      const value = Object.entries(BUDGET_LABELS).find(
                        ([, itemLabel]) => itemLabel === label,
                      )?.[0] as UserPreference['budget_level'];
                      setPreference(current => current && ({
                        ...current,
                        budget_level: value,
                      }));
                    }}
                    single
                  />
                </QuestionBlock>
                <div className="grid gap-3 sm:grid-cols-2">
                  <ToggleCard
                    label="优先室内"
                    description="天气不稳定时优先选择室内地点"
                    checked={preference.prefer_indoor}
                    onChange={checked => setPreference(current => current && ({
                      ...current,
                      prefer_indoor: checked,
                    }))}
                  />
                  <ToggleCard
                    label="尽量少排队"
                    description="优先考虑等待时间更短的候选"
                    checked={preference.prefer_low_wait}
                    onChange={checked => setPreference(current => current && ({
                      ...current,
                      prefer_low_wait: checked,
                    }))}
                  />
                </div>
              </div>
            )}
          </div>

          {error && (
            <p className="mt-4 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </p>
          )}
          {saved && (
            <p className="mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
              偏好已保存，正在返回首页...
            </p>
          )}

          <div className="mt-7 flex items-center justify-between border-t border-slate-100 pt-5">
            <button
              type="button"
              onClick={() => setStep(current => Math.max(0, current - 1))}
              disabled={step === 0 || saving}
              className="min-h-11 rounded-xl border border-slate-200 bg-white px-5 text-sm font-bold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              上一步
            </button>
            {step < 3 ? (
              <button
                type="button"
                onClick={() => setStep(current => Math.min(3, current + 1))}
                className="min-h-11 rounded-xl bg-blue-600 px-6 text-sm font-bold text-white transition hover:bg-blue-700"
              >
                下一步
              </button>
            ) : (
              <button
                type="button"
                onClick={save}
                disabled={saving || saved}
                className="min-h-11 rounded-xl bg-blue-600 px-6 text-sm font-bold text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? '正在保存...' : '保存偏好'}
              </button>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}


function ChoiceGrid({
  options,
  selected,
  onSelect,
  single = false,
}: {
  options: string[];
  selected: string[];
  onSelect: (value: string) => void;
  single?: boolean;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {options.map(option => {
        const isSelected = selected.includes(option);
        return (
          <button
            key={option}
            type="button"
            aria-pressed={isSelected}
            onClick={() => onSelect(option)}
            className={`min-h-16 rounded-2xl border px-4 py-3 text-left text-sm font-bold transition ${
              isSelected
                ? 'border-blue-500 bg-blue-50 text-blue-800 ring-2 ring-blue-100'
                : 'border-slate-200 bg-white text-slate-700 hover:border-blue-300 hover:bg-slate-50'
            } ${single ? 'sm:min-h-20' : ''}`}
          >
            <span className="flex items-center justify-between gap-3">
              {option}
              <span
                aria-hidden="true"
                className={`h-4 w-4 rounded-full border ${
                  isSelected
                    ? 'border-blue-600 bg-blue-600 ring-2 ring-blue-100'
                    : 'border-slate-300'
                }`}
              />
            </span>
          </button>
        );
      })}
    </div>
  );
}


function QuestionBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-3 text-sm font-bold text-slate-700">{title}</p>
      {children}
    </div>
  );
}


function ToggleCard({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className={`flex cursor-pointer gap-3 rounded-2xl border p-4 transition ${
      checked ? 'border-blue-400 bg-blue-50' : 'border-slate-200 bg-white'
    }`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={event => onChange(event.target.checked)}
        className="mt-0.5 h-4 w-4 accent-blue-600"
      />
      <span>
        <span className="block text-sm font-bold text-slate-800">{label}</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">
          {description}
        </span>
      </span>
    </label>
  );
}
