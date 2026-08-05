# قرارداد Wrapper برای MatchPulse v1

این سند قرارداد HTTP نرمال‌شده‌ای را تعریف می‌کند که هر football data wrapper پیش از اتصال به MatchPulse v2 باید پیاده‌سازی کند. هدف، جدا نگه‌داشتن core اپلیکیشن از جزئیات provider و ایجاد رفتار یکسان در محیط‌های local و server است.

## ۱. هدف قرارداد

MatchPulse باید بتواند داده مسابقات، تیم‌ها، وضعیت زنده و رویدادها را از wrapperهای مختلف با یک شکل پایدار مصرف کند. این قرارداد مرز مشترک میان Competition Data Dispatcher و هر Competition Wrapper است و به provider خام، زبان پاسخ provider، روش authentication یا ساختار storage آن وابسته نیست.

مسیر مجاز داده فقط به شکل زیر است:

```text
MatchPulse
  -> Competition Data Dispatcher
  -> Competition Wrapper
  -> External Provider
```

MatchPulse core نباید مستقیماً به Varzesh3، football-data.org، API-Sports یا هیچ provider بیرونی دیگری متصل شود. همچنین وجود wrapper نباید با fallback مستقیم از core به provider دور زده شود.

## ۲. مرز مسئولیت MatchPulse و Wrapper

مسئولیت MatchPulse:

- انتخاب competition و season از طریق Competition Data Dispatcher.
- مصرف پاسخ‌های نرمال‌شده این قرارداد.
- ترکیب داده فوتبال با اطلاعات کاربر، علاقه‌مندی‌ها، پیش‌بینی‌ها، یادآورها و اعلان‌ها.
- استفاده از `id` پایدار wrapper به‌عنوان هویت اصلی entity.
- مستقل ماندن از authentication، field nameها و status codeهای داخلی provider.

مسئولیت Wrapper:

- مدیریت authentication و secretهای provider.
- دریافت داده، retry محدود، caching و رعایت rate limit.
- نگهداری mapping میان شناسه‌های داخلی wrapper و شناسه‌های provider.
- تبدیل نام تیم‌ها، زمان‌ها، statusها، scoreها و eventها به قرارداد نرمال‌شده.
- ارائه fallback از cache یا stale data در صورت مناسب بودن، بدون ساختن داده جعلی.
- پنهان‌کردن provider internals از MatchPulse core.

## ۳. قوانین عمومی HTTP و JSON

- همه endpointها باید پاسخ UTF-8 JSON برگردانند.
- پاسخ موفق باید HTTP status معتبر، معمولاً `200`, داشته باشد.
- `matches`، `teams`، `standings` و `events` همیشه array هستند؛ نبود داده با `[]` نمایش داده می‌شود، نه `null`.
- مقدار optional ناموجود باید `null` باشد. wrapper نباید برای پرکردن فیلدها مقدار جعلی تولید کند.
- score باید number یا `null` باشد. مقدار `0` یک score معتبر است و نباید با نبود score اشتباه گرفته شود.
- Booleanها باید JSON boolean واقعی باشند، نه stringهایی مانند `"TRUE"` یا `"false"`.
- field nameها، endpointها، status valueها و technical termهای این قرارداد به English باقی می‌مانند.
- wrapper می‌تواند fieldهای نرمال‌شده بیشتری اضافه کند، به شرطی که معنای fieldهای v1 را تغییر ندهد.
- MatchPulse در local و server باید همین قرارداد را مصرف کند؛ تفاوت محیط نباید response shape را تغییر دهد.

## ۴. قوانین Stable ID

- `id` شناسه پایدار داخلی wrapper برای match یا team و هویت اصلی مصرف‌شده توسط MatchPulse است.
- یک entity یکسان باید در refreshها، restartها و محیط‌های local/server همان `id` را حفظ کند.
- `internal_match_id` در صورت وجود باید با identity داخلی wrapper سازگار باشد؛ در قرارداد فعلی `id` همچنان کلید اصلی MatchPulse است.
- `external_match_id` شناسه provider و صرفاً metadata برای tracing، debugging و mapping است.
- MatchPulse نباید `external_match_id` را به‌عنوان primary identity استفاده کند.
- تغییر provider نباید باعث تغییر `id` موجود برای entityهای قبلاً منتشرشده شود.
- event `id` در صورت ارائه باید برای همان provider و match پایدار باشد تا deduplication ممکن شود.
- اگر provider برای event شناسه پایدار ندارد، wrapper می‌تواند `id` را `null` بگذارد؛ ساخت شناسه باید deterministic باشد، نه تصادفی در هر request.

## ۵. قوانین Timestamp و timezone

- `kickoff_utc` زمان canonical شروع مسابقه است و باید در قالب ISO 8601 UTC مانند `2026-06-29T20:30:00Z` ارائه شود.
- `kickoff` می‌تواند همان مقدار canonical یا یک timestamp نرمال‌شده سازگار باشد، اما نباید با `kickoff_utc` تناقض داشته باشد.
- `source_timezone` در صورت وجود metadata مربوط به منبع است و نباید MatchPulse را مجبور به شناخت timezone provider کند.
- `date` و `local_date` convenience field هستند و جای `kickoff_utc` را نمی‌گیرند.
- `date_iran`، `time_iran` و `datetime_iran` convenience fieldهای localized هستند. اگر wrapper آن‌ها را ارائه می‌کند، باید با `kickoff_utc` سازگار و در refreshهای بعدی پایدار باشند.
- تبدیل timezone فقط در wrapper انجام می‌شود. MatchPulse core نباید زمان نرمال‌شده wrapper را دوباره تبدیل کند.
- اگر زمان دقیق ناموجود است، `kickoff_utc` باید `null` باشد؛ wrapper نباید ساعت تخمینی را به‌عنوان زمان قطعی منتشر کند.
- `last_updated` در صورت ارائه باید timestamp قابل parse باشد و زمان آخرین به‌روزرسانی داده نرمال‌شده را نشان دهد.

## ۶. نرمال‌سازی وضعیت مسابقه

حداقل statusهای نرمال‌شده v1 عبارت‌اند از:

- `upcoming`: مسابقه شروع نشده است.
- `live`: مسابقه یا یکی از phaseهای فعال آن در جریان است.
- `finished`: نتیجه مسابقه قطعی و پایان آن توسط provider تأیید شده است.

قواعد status:

- `status` باید provider-independent باشد و از raw status provider ترجمه شود.
- `is_live` باید با `status` سازگار باشد؛ برای `live` مقدار `true` و برای `upcoming` یا `finished` مقدار `false` است.
- `status_title` یک label نرمال‌شده یا قابل نمایش است و جایگزین `status` نیست.
- `live_badge`، `live_phase` و `minute` جزئیات optional وضعیت زنده‌اند.
- halftime، extra time و penalty shootout در حال اجرا باید همچنان `status: "live"` داشته باشند، نه `finished`.
- نبود minute، خاموش بودن `live_badge` یا حذف موقت مسابقه از feed زنده به‌تنهایی نشانه `finished` نیست.
- `pending_result` در وضعیت فعلی یک state مشتق‌شده در لایه application خود MatchPulse است و در Contract v1 یک status الزامی برای wrapper محسوب نمی‌شود.
- statusهای جدید فقط در صورت تعریف معنای provider-independent و با رعایت backward compatibility اضافه می‌شوند.

## ۷. `GET /matches`

این endpoint فهرست نرمال‌شده مسابقات competition wrapper را برمی‌گرداند.

نمونه پاسخ کوتاه‌شده:

```json
{
  "ok": true,
  "count": 1,
  "matches": [
    {
      "id": 75,
      "internal_match_id": 75,
      "external_match_id": "441745",
      "provider": "varzesh3",
      "home_en": "Netherlands",
      "home_fa": "هلند",
      "away_en": "Morocco",
      "away_fa": "مراکش",
      "home_flag": "🇳🇱",
      "away_flag": "🇲🇦",
      "home_logo": null,
      "away_logo": null,
      "home_team_id": 18,
      "away_team_id": 31,
      "kickoff": "2026-06-29T01:00:00Z",
      "kickoff_utc": "2026-06-29T01:00:00Z",
      "date_iran": "1405/04/08",
      "time_iran": "04:30",
      "group": "R32",
      "stage": "r32",
      "stage_label": "R32",
      "stadium": null,
      "city": null,
      "status": "finished",
      "status_title": "Finished",
      "is_live": false,
      "live_badge": null,
      "live_phase": null,
      "minute": null,
      "home_score": 1,
      "away_score": 1,
      "score": "1 - 1",
      "home_penalty_score": 2,
      "away_penalty_score": 3,
      "penalty_winner_side": "away",
      "penalty_winner_en": "Morocco",
      "penalty_winner_fa": "مراکش",
      "penalty_summary_fa": "مراکش در ضربات پنالتی ۳ - ۲ پیروز شد",
      "penalty_summary_en": "Morocco won 3 - 2 on penalties",
      "win_method": "penalty_shootout",
      "result": "1 - 1",
      "last_updated": "2026-06-29T04:15:00Z"
    }
  ]
}
```

فیلدهای نرمال‌شده مشاهده‌شده در match:

- Identity: `id`, `internal_match_id`, `external_match_id`, `provider`
- Teams: `home_en`, `home_fa`, `away_en`, `away_fa`, `home_flag`, `away_flag`, `home_logo`, `away_logo`, `home_team_id`, `away_team_id`
- Time: `kickoff`, `kickoff_utc`, `source_timezone`, `date`, `local_date`, `date_iran`, `time_iran`, `datetime_iran`
- Competition: `group`, `stage`, `stage_label`
- Location: `stadium`, `city`
- State: `status`, `status_title`, `is_live`, `live_badge`, `live_phase`, `minute`
- Score: `home_score`, `away_score`, `score`, `result`
- Penalties: `home_penalty_score`, `away_penalty_score`, `penalty_winner_side`, `penalty_winner_en`, `penalty_winner_fa`, `penalty_summary_fa`, `penalty_summary_en`, `win_method`
- Freshness: `last_updated`

در مسابقات حذفی، participant ناشناخته می‌تواند با label نرمال‌شده‌ای مانند `Winner Match 74` نمایش داده شود. wrapper نباید placeholder معتبر را به string خالی تبدیل کند.

## ۸. `GET /teams`

این endpoint فهرست نرمال‌شده تیم‌های competition را برمی‌گرداند.

```json
{
  "ok": true,
  "teams": [
    {
      "id": 31,
      "external_team_id": "31",
      "provider": "varzesh3",
      "name_en": "Morocco",
      "name_fa": "مراکش",
      "short_name": "MAR",
      "flag": "🇲🇦",
      "logo": null,
      "group": "C"
    }
  ]
}
```

`id` هویت پایدار تیم در wrapper است. `external_team_id` و `provider` metadata اختیاری برای tracing هستند. حداقل یکی از `name_en` یا `name_fa` باید مقدار قابل نمایش داشته باشد؛ wrapper در صورت دسترسی بهتر است هر دو را ارائه کند.

## ۹. `GET /standings`

این endpoint capability-dependent است و فقط وقتی الزامی است که competition در registry مقدار `supports_standings: true` داشته باشد.

```json
{
  "ok": true,
  "standings": [
    {
      "team_id": 31,
      "team": "Morocco",
      "team_en": "Morocco",
      "team_fa": "مراکش",
      "group": "C",
      "rank": 1,
      "played": 3,
      "wins": 2,
      "draws": 1,
      "losses": 0,
      "goals_for": 5,
      "goals_against": 2,
      "goal_difference": 3,
      "points": 7,
      "flag": "🇲🇦",
      "logo": null
    }
  ]
}
```

مقادیر آماری باید number باشند. `team_id` باید با `id` تیم در `/teams` سازگار باشد. `flag` و `logo` optional هستند. برای competition بدون standings، capability باید غیرفعال باشد و MatchPulse نباید این endpoint را required فرض کند.

## ۱۰. `GET /match/{match_id}/live`

`match_id` همان `id` پایدار wrapper است، نه `external_match_id`.

```json
{
  "ok": true,
  "match": {
    "id": 75,
    "internal_match_id": 75,
    "external_match_id": "441745",
    "provider": "varzesh3",
    "home_en": "Netherlands",
    "home_fa": "هلند",
    "away_en": "Morocco",
    "away_fa": "مراکش",
    "kickoff_utc": "2026-06-29T01:00:00Z",
    "status": "live",
    "status_title": "Penalty shootout",
    "is_live": true,
    "live_badge": "Penalty shootout",
    "live_phase": "penalty_shootout",
    "minute": null,
    "raw_minute": null,
    "home_score": 1,
    "away_score": 1,
    "home_penalty_score": 2,
    "away_penalty_score": 1,
    "stadium": null,
    "city": null,
    "video_url": null,
    "summary_url": null
  }
}
```

شیء `match` باید همان identity، team، kickoff، status، score، penalty و location fieldهای `/matches` را استفاده کند. `raw_minute`، `video_url` و `summary_url` optional هستند. وجود penalty score در وضعیت `live` نباید winner نهایی یا عبارت `won on penalties` تولید کند.

## ۱۱. `GET /match/{match_id}/events`

این endpoint رویدادهای نرمال‌شده یک match را برمی‌گرداند و `events` همیشه array است.

```json
{
  "ok": true,
  "match_id": 34,
  "external_match_id": "441704",
  "provider": "varzesh3",
  "home_penalty_score": null,
  "away_penalty_score": null,
  "penalty_winner_side": null,
  "penalty_winner_en": null,
  "penalty_winner_fa": null,
  "penalty_summary_fa": null,
  "penalty_summary_en": null,
  "win_method": null,
  "events": [
    {
      "id": "2874946",
      "minute": 7,
      "raw_minute": "7",
      "type": "card",
      "raw_type": 2,
      "normalized_type": "yellow_card",
      "label_fa": "کارت زرد",
      "label_en": "Yellow card",
      "icon": "🟨",
      "is_scoring_event": false,
      "team": "Morocco",
      "team_side": "home",
      "team_name": "Morocco",
      "player": "Player Name",
      "assist": null,
      "description": null,
      "video_url": null,
      "created_at": null
    }
  ]
}
```

قواعد event:

- `normalized_type` باید provider-independent و extensible باشد.
- هر wrapper باید raw event typeهای provider را به نام‌های نرمال‌شده MatchPulse ترجمه کند.
- نمونه‌های تأییدشده فعلی شامل `yellow_card` و `substitution` هستند.
- قابلیت‌های MatchPulse به پشتیبانی نرمال‌شده رویدادهای مهم فوتبال مانند goalها، cardها، substitutionها و match phaseها نیاز دارند؛ این سند raw valueهای تأییدنشده provider را تعریف نمی‌کند.
- `team_side` فقط یکی از `home`، `away` یا `null` است. مقدار `null` برای رویدادی استفاده می‌شود که قابل انتساب قطعی به یک طرف نیست.
- `is_scoring_event` باید فقط معنای scoring قطعی داشته باشد. رویدادهای نامعتبرشده، missed penalty و phase event نباید scoring اعلام شوند.
- `label_fa` و `label_en` label نمایشی‌اند و `normalized_type` کلید منطقی پایدار است.
- `type` و `raw_type` metadata سازگاری/debug هستند و core نباید منطق provider را بر پایه آن‌ها بسازد.

## ۱۲. Required fields در برابر Optional fields

### Contract-required response fields

- `/matches`: `ok`, `count`, `matches`
- `/teams`: `ok`, `teams`
- `/match/{match_id}/live`: `ok`, `match`
- `/match/{match_id}/events`: `ok`, `match_id`, `events`
- `/standings` در صورت فعال بودن capability: `ok`, `standings`

### Contract-required match fields

- `id`
- `home_en`, `home_fa`, `away_en`, `away_fa`؛ برای هر طرف حداقل یک نام یا placeholder معتبر باید قابل نمایش باشد.
- `kickoff_utc`
- `status`
- `is_live`
- `home_score`, `away_score`

کلیدهای required باید در response حضور داشته باشند؛ مقدار فیلدهایی مانند `kickoff_utc` یا score پیش از مشخص‌شدن می‌تواند `null` باشد.

### Contract-required team fields

- `id`
- `name_en`, `name_fa`؛ حداقل یکی باید مقدار قابل نمایش داشته باشد.

### Contract-required event fields

- `id`
- `minute`
- `raw_minute`
- `normalized_type`
- `is_scoring_event`
- `team_side`
- `player`
- `description`

مقادیر unavailable می‌توانند `null` باشند، اما `events` باید array باقی بماند.

### Optional normalized fields

- localized labels و media: `flag`, `logo`, `label_fa`, `label_en`, `icon`, `video_url`, `summary_url`
- convenience time fields: `date`, `local_date`, `date_iran`, `time_iran`, `datetime_iran`
- live details: `status_title`, `live_badge`, `live_phase`, `minute`, `raw_minute`
- location: `stadium`, `city`
- freshness: `last_updated`

### Provider/debug metadata

- `provider`
- `external_match_id`
- `external_team_id`
- `raw_type`
- `source_timezone`

این fieldها ممکن است برای tracing مفید باشند، اما MatchPulse core نباید برای رفتار اصلی به آن‌ها وابسته شود.

### Competition-specific fields

- group/stage: `group`, `stage`, `stage_label`
- knockout/penalties: `home_penalty_score`, `away_penalty_score`, `penalty_winner_side`, `penalty_winner_en`, `penalty_winner_fa`, `penalty_summary_fa`, `penalty_summary_en`, `win_method`
- standings statistics و knockout participant labelها

این fieldها در competitionهایی که مفهوم متناظر ندارند optional هستند و باید `null` یا غایب باشند، بدون اینکه core مجبور به شناخت provider شود.

## ۱۳. Provider identity isolation

- MatchPulse فقط contract entityها را می‌شناسد و provider-specific fieldها را وارد business logic نمی‌کند.
- credential، token، raw endpoint، raw status و provider-specific enum داخل wrapper باقی می‌مانند.
- `provider` و `external_*_id` فقط برای observability، support و debugging قابل استفاده‌اند.
- Competition Data Dispatcher wrapper مناسب را بر اساس competition/season انتخاب می‌کند؛ UI و core نباید provider selector داشته باشند.
- هیچ direct external-provider fallback در MatchPulse core مجاز نیست.
- تغییر provider باید تا حد ممکن بدون تغییر API مصرفی MatchPulse انجام شود.

## ۱۴. رفتار Error و Availability

به دلیل تفاوت implementationها، v1 یک error schema سخت و کامل تعریف نمی‌کند. حداقل اصول عبارت‌اند از:

- استفاده از HTTP status code معتبر برای success، client error و server/upstream error.
- پاسخ error باید JSON باشد؛ HTML error page مجاز نیست.
- fieldهای `error` و `warning` می‌توانند برای توضیح machine-readable یا human-readable اضافه شوند.
- provider unavailable نباید به سکوت با داده fabricated تبدیل شود.
- اگر cache معتبر موجود است، wrapper می‌تواند آن را با indicatorی مانند `stale: true` برگرداند.
- اگر داده‌ای در provider وجود ندارد، array خالی معتبر است؛ اگر دریافت داده شکست خورده است، wrapper باید تفاوت را با status، `warning` یا `error` آشکار کند.
- endpoint رویدادها در failure موقت نباید cache غیرخالی موجود را با `[]` جایگزین کند.
- اطلاعات حساس، token و credential نباید در response یا log افشا شوند.

نمونه حداقلی و غیرالزام‌آور:

```json
{
  "ok": false,
  "events": [],
  "warning": "Upstream data is temporarily unavailable"
}
```

## ۱۵. Caching، Stale Data و Rate Limit

- wrapper باید برای کاهش latency و جلوگیری از درخواست اضافی، caching متناسب با نوع داده داشته باشد.
- TTL داده زنده می‌تواند کوتاه‌تر از teams، schedule یا standings باشد.
- stale-data fallback در outage کوتاه‌مدت مجاز است، به شرطی که stale بودن پنهان نشود.
- cache خالی ناشی از timeout نباید داده غیرخالی قبلی را نابود کند.
- polling، retry و backoff باید محدود باشند و باعث spam به provider نشوند.
- rate limit باید داخل wrapper مدیریت شود و core نباید provider-specific quota را بداند.
- در worldcup2026 فعلی header مشاهده‌شده برابر 500 request در 60 seconds است؛ این عدد implementation-specific است و requirement عمومی قرارداد نیست.
- cache و restart نباید Stable IDها یا ترتیب معنایی داده را تغییر دهند.

## ۱۶. قوانین Capability

Endpointهای required هسته قرارداد:

- `GET /matches`
- `GET /teams`
- `GET /match/{match_id}/live`
- `GET /match/{match_id}/events`

Endpoint وابسته به capability:

- `GET /standings` فقط وقتی `supports_standings: true` است.

هر competition registry باید capabilityهای قابل اتکا را صادقانه اعلام کند. وجود route بدون داده واقعی نباید باعث فعال‌شدن capability شود. قابلیت‌های آینده مانند videos، summaries یا lineups باید به‌صورت additive و versioned تعریف شوند.

## ۱۷. Backward Compatibility و Contract Versioning

- این سند Contract v1 است.
- اضافه‌کردن field optional جدید، در صورتی که معنای fieldهای قبلی تغییر نکند، backward-compatible است.
- حذف field required، تغییر type، تغییر معنای `id`، تغییر status semantics یا تغییر response root breaking change محسوب می‌شود.
- breaking change به contract version جدید نیاز دارد.
- wrapper باید migration window کافی برای consumerهای نسخه قبلی فراهم کند.
- MatchPulse می‌تواند fieldهای ناشناخته را نادیده بگیرد، اما wrapper نباید انتظار داشته باشد core provider-specific fieldها را تفسیر کند.
- local و production باید هم‌زمان روی contract version سازگار اجرا شوند.

## ۱۸. Checklist اتصال Wrapper جدید

- [ ] مسیر داده فقط `MatchPulse -> Competition Data Dispatcher -> Competition Wrapper -> External Provider` است.
- [ ] secretها و authentication فقط داخل wrapper مدیریت می‌شوند.
- [ ] `GET /matches` پاسخ نرمال‌شده و `matches: []` پایدار دارد.
- [ ] `GET /teams` پاسخ نرمال‌شده و `teams: []` پایدار دارد.
- [ ] `GET /match/{match_id}/live` از همان `id` و field semantics فهرست مسابقات استفاده می‌کند.
- [ ] `GET /match/{match_id}/events` همیشه `events` array و event typeهای provider-independent دارد.
- [ ] `GET /standings` فقط در صورت `supports_standings: true` ارائه می‌شود.
- [ ] `id`ها در refresh، restart، local و server پایدارند.
- [ ] `external_match_id` و `provider` فقط metadata هستند.
- [ ] `kickoff_utc` ISO 8601 UTC است و timezone دوباره در core تبدیل نمی‌شود.
- [ ] scoreها number یا `null` هستند و finished `0-0` درست حفظ می‌شود.
- [ ] statusهای `upcoming`, `live`, `finished` به‌درستی normalize می‌شوند.
- [ ] halftime، extra time و live penalty shootout اشتباهاً `finished` نمی‌شوند.
- [ ] optional value ناموجود `null` است و fabricated data تولید نمی‌شود.
- [ ] خطاها JSON هستند و HTML error page برنمی‌گردد.
- [ ] caching، stale fallback، retry و rate-limit handling تست شده‌اند.
- [ ] پاسخ‌ها UTF-8 و نام‌های فارسی/انگلیسی قابل نمایش‌اند.
- [ ] هیچ direct provider fallback داخل MatchPulse core وجود ندارد.
- [ ] contract testها در local و server خروجی سازگار دارند.

## ۱۹. وضعیت فعلی انطباق worldcup2026

بر اساس responseهای واقعی مشاهده‌شده، wrapper فعلی worldcup2026 مبنای Contract v1 است و وضعیت آن چنین ارزیابی می‌شود:

- `GET /matches`: پیاده‌سازی شده و root شامل `ok`, `count`, `matches` است؛ fieldهای identity، تیم، زمان، stage، status، score و penalty را ارائه می‌کند.
- `GET /teams`: پیاده‌سازی شده و team identity، نام‌های localized، flag/logo و group را ارائه می‌کند.
- `GET /match/{match_id}/live`: پیاده‌سازی شده و match object نرمال‌شده همراه با live، score و media linkهای optional برمی‌گرداند.
- `GET /match/{match_id}/events`: پیاده‌سازی شده و eventهای نرمال‌شده با Stable ID، `normalized_type`, label و `is_scoring_event` ارائه می‌کند.
- `GET /standings`: در registry فعلی MatchPulse برای worldcup2026 مقدار `supports_standings: false` است؛ بنابراین در وضعیت فعلی capability الزامی محسوب نمی‌شود.
- time، penalty summary، placeholder knockout team و event normalization در پاسخ‌های فعلی پوشش داده شده‌اند.
- rate-limit مشاهده‌شده 500 request در 60 seconds متعلق به implementation فعلی است و بخشی از Contract v1 عمومی نیست.

این snapshot گواه تضمین دائمی نیست. پیش از هر deployment باید responseهای wrapper با checklist همین سند و contract testهای local/server دوباره بررسی شوند.
