# قرارداد Multi-Competition Wrapper برای MatchPulse v2

این سند قرارداد HTTP نرمال‌شده wrapper عمومی فوتبال برای MatchPulse v2 را تعریف می‌کند. Contract v2 دامنه Contract v1 را از یک competition به چند competition و چند season گسترش می‌دهد، بدون اینکه MatchPulse core را به رفتار یا ساختار هیچ provider خاصی وابسته کند.

## ۱. هدف Contract v2

هدف Contract v2 ایجاد یک interface پایدار برای دریافت داده فوتبال از competitionها و seasonهای مختلف است. MatchPulse باید بتواند با استفاده از `competition_key` و `season_key` داده مسابقات، تیم‌ها، standings، وضعیت زنده و eventها را مصرف کند، بدون اینکه `league_id`، `season_id`، raw status یا pagination provider را بشناسد.

اصول اصلی:

- یک Generic Football Wrapper می‌تواند چند competition و season را مدیریت کند.
- تمام داده‌های خروجی پیش از رسیدن به MatchPulse normalize می‌شوند.
- providerهای جدید باید با Provider Adapter اضافه شوند، نه با تغییر business logic در MatchPulse.
- رفتار local و server باید بر اساس یک contract یکسان باشد.
- هیچ direct provider fallback در MatchPulse core مجاز نیست.

## ۲. Scope و سازگاری با Contract v1

- [Contract v1](MATCHPULSE_WRAPPER_CONTRACT_V1.md) و wrapper فعلی `worldcup2026` معتبر و بدون تغییر باقی می‌مانند.
- Contract v1 قرارداد wrapper تک‌رقابتی موجود است و برای حفظ backward compatibility ادامه پیدا می‌کند.
- Contract v2 قرارداد Generic Football Wrapper آینده است و endpointهای آن competition-aware و season-aware هستند.
- پیاده‌سازی Contract v2 نباید endpoint، response shape یا Stable IDهای Contract v1 را بدون migration صریح تغییر دهد.
- MatchPulse می‌تواند در دوره مهاجرت، wrapperهای v1 و v2 را هم‌زمان از طریق Competition Data Dispatcher مصرف کند.
- این سند prediction، reminder، notification، user profile یا frontend API را بازتعریف نمی‌کند.

## ۳. معماری Multi-Competition

مسیر مجاز داده در Contract v2:

```text
MatchPulse
  -> Competition Data Dispatcher
  -> Generic Football Wrapper
  -> Provider Adapter
  -> External Provider
```

نقش لایه‌ها:

- MatchPulse: مصرف داده نرمال‌شده و ترکیب آن با قابلیت‌های اپلیکیشن.
- Competition Data Dispatcher: انتخاب wrapper و source مناسب برای `competition_key` و `season_key`.
- Generic Football Wrapper: registry، caching، identity mapping و contract normalization.
- Provider Adapter: authentication، provider endpointها، raw field mapping، pagination و rate-limit handling.
- External Provider: منبع خام داده؛ provider اولیه Varzesh3 است.

Provider Adapterهای آینده می‌توانند اضافه شوند، اما MatchPulse نباید تفاوت رفتار providerها را مشاهده یا تفسیر کند.

## ۴. قرارداد Competition Registry

### `GET /competitions`

این endpoint competitionهای ثبت‌شده در Generic Football Wrapper را برمی‌گرداند.

```json
{
  "ok": true,
  "count": 1,
  "competitions": [
    {
      "competition_key": "worldcup2026",
      "name_fa": "جام جهانی ۲۰۲۶",
      "name_en": "World Cup 2026",
      "type": "international",
      "status": "archived",
      "is_active": true,
      "capabilities": {
        "supports_matches": true,
        "supports_teams": true,
        "supports_standings": false,
        "supports_live": true,
        "supports_events": true
      }
    }
  ]
}
```

قواعد:

- `competition_key` شناسه business پایدار MatchPulse است.
- `competition_key` نباید از provider `league_id` به‌عنوان business identifier استفاده کند.
- `competitions` همیشه array است.
- `name_fa` یا `name_en` می‌تواند در صورت نبود داده معتبر `null` باشد، اما حداقل یک نام نمایشی باید موجود باشد.
- capabilityها باید وضعیت واقعی data source را نشان دهند، نه صرفاً وجود route را.

## ۵. قرارداد Season Registry

### `GET /competitions/{competition_key}/seasons`

```json
{
  "ok": true,
  "competition_key": "worldcup2026",
  "count": 1,
  "seasons": [
    {
      "competition_key": "worldcup2026",
      "season_key": "2026",
      "name_fa": "جام جهانی ۲۰۲۶",
      "name_en": "World Cup 2026",
      "status": "archived",
      "is_default": true,
      "capabilities": {
        "supports_matches": true,
        "supports_teams": true,
        "supports_standings": false,
        "supports_live": true,
        "supports_events": true
      }
    }
  ]
}
```

قواعد:

- `season_key` شناسه business پایدار season در محدوده `competition_key` است.
- `season_key` نباید مستقیماً provider `season_id` باشد، مگر اینکه wrapper پایداری آن را به‌عنوان mapping داخلی تضمین کند؛ MatchPulse همچنان فقط `season_key` را می‌شناسد.
- ترکیب `competition_key` و `season_key` scope اصلی داده‌های season است.
- در هر competition حداکثر یک season باید `is_default: true` داشته باشد.
- `seasons` همیشه array است و نبود season با `[]` نمایش داده می‌شود.

## ۶. مدل Capability

Capabilityها می‌توانند در سطح competition و season تعریف شوند. مقدار season-specific در صورت وجود دقیق‌تر است و باید بر مقدار عمومی competition اولویت داشته باشد.

Capabilityهای پایه v2:

- `supports_matches`
- `supports_teams`
- `supports_standings`
- `supports_live`
- `supports_events`

قواعد:

- endpointهای matches، teams، live و events اجزای required Contract v2 برای source پیکربندی‌شده هستند.
- standings capability-dependent است.
- اگر `supports_standings: false` باشد، endpoint standings می‌تواند `404` یا `501` برگرداند.
- نبود standings نباید matches، teams، live یا events را از کار بیندازد.
- MatchPulse نباید فرض کند همه tournamentها یک جدول تخت دارند.
- grouped standings یا multi-table standings در آینده باید به‌صورت additive و versioned اضافه شوند.

## ۷. قوانین Stable Identity

- `id` شناسه canonical و پایدار entity در Generic Football Wrapper است.
- MatchPulse باید match و team را با `id` مصرف کند، نه `external_match_id` یا `external_team_id`.
- match `id` باید در discovery windowها، refreshها، paginationها، cacheها، restartها و محیط‌های local/server ثابت بماند.
- team `id` باید میان matches، teams، standings، live و events سازگار باشد.
- `competition_key` و `season_key` بخشی از scope هر match و team هستند.
- `provider` و `external_*_id` metadata لازم برای mapping و tracing هستند، اما business identity MatchPulse نیستند.
- provider `league_id` و `season_id` فقط metadata داخلی Adapter هستند.
- تغییر provider نباید Stable IDهای منتشرشده را بدون migration کنترل‌شده تغییر دهد.
- event `id` در صورت وجود باید برای ترکیب provider و match پایدار باشد تا deduplication قابل اتکا باشد.
- matchهایی که در چند discovery window دیده می‌شوند باید پیش از normalization با provider match ID deduplicate شوند.

### قانون team ID صفر

Varzesh3 fixtures ممکن است `host.id: 0` یا `guest.id: 0` برگرداند. مقدار `0` هرگز نباید canonical normalized team ID شود.

Adapter باید identity تیم را از داده معتبر بازیابی کند، از جمله:

- team link pathها
- season matches
- standings
- provider team map موجود

اگر identity با اطمینان resolve نشد، wrapper باید warning یا unresolved identity state صریح ارائه کند و نباید ID جعلی بسازد.

## ۸. Metadata مربوط به Competition و Season

هر normalized match و team باید `competition_key` و `season_key` داشته باشد. این fieldها توسط registry و provider mapping تعیین می‌شوند، نه با حدس‌زدن از title خام provider.

Provider Adapter می‌تواند metadata زیر را به‌صورت داخلی نگه دارد:

- `provider`
- `provider_league_id`
- `provider_season_id`
- provider title و source URL

این metadata نباید برای routing یا business logic به MatchPulse core نشت کند. فقط `provider` و `external_*_id` طبق endpoint contract در response نرمال‌شده منتشر می‌شوند؛ metadata خام بیشتر باید optional/debug-only باشد.

## ۹. Endpoint مسابقات

### `GET /competitions/{competition_key}/seasons/{season_key}/matches`

هر normalized match حداقل باید fieldهای زیر را داشته باشد:

- `id`
- `competition_key`
- `season_key`
- `provider`
- `external_match_id`
- `home_team_id`
- `away_team_id`
- `kickoff_utc`
- `status`
- `is_live`
- `home_score`
- `away_score`

نمونه پاسخ کوتاه‌شده:

```json
{
  "ok": true,
  "competition_key": "worldcup2026",
  "season_key": "2026",
  "count": 1,
  "matches": [
    {
      "id": 75,
      "competition_key": "worldcup2026",
      "season_key": "2026",
      "provider": "varzesh3",
      "external_match_id": "441745",
      "home_team_id": 18,
      "away_team_id": 31,
      "home_en": "Netherlands",
      "home_fa": "هلند",
      "away_en": "Morocco",
      "away_fa": "مراکش",
      "home_logo": null,
      "away_logo": null,
      "kickoff_utc": "2026-06-29T01:00:00Z",
      "status": "finished",
      "is_live": false,
      "live_phase": null,
      "home_score": 1,
      "away_score": 1,
      "home_penalty_score": 2,
      "away_penalty_score": 3,
      "stage": "r32",
      "group": "R32",
      "last_updated": "2026-06-29T04:15:00Z"
    }
  ]
}
```

قواعد:

- `matches` همیشه array است.
- score باید number یا `null` باشد؛ finished `0-0` نباید missing score تلقی شود.
- `home_team_id` و `away_team_id` باید canonical team ID باشند یا در صورت unresolved بودن طبق بخش ۱۸ رفتار شود.
- fieldهای اضافی Contract v1 مانند localized names، flags، location، stage، group، penalties، result و convenience time fieldها می‌توانند حفظ شوند.
- wrapper نباید recordهای تکراری یک provider match را در خروجی منتشر کند.

## ۱۰. Endpoint تیم‌ها

### `GET /competitions/{competition_key}/seasons/{season_key}/teams`

هر normalized team باید fieldهای زیر را داشته باشد:

- `id`
- `competition_key`
- `season_key`
- `provider`
- `external_team_id`
- `name_fa`
- `name_en`
- `logo`

```json
{
  "ok": true,
  "competition_key": "worldcup2026",
  "season_key": "2026",
  "count": 1,
  "teams": [
    {
      "id": 31,
      "competition_key": "worldcup2026",
      "season_key": "2026",
      "provider": "varzesh3",
      "external_team_id": "31",
      "name_fa": "مراکش",
      "name_en": "Morocco",
      "logo": null
    }
  ]
}
```

قواعد:

- `teams` همیشه array است.
- `name_en` ممکن است در نسخه اولیه `null` باشد، اگر provider فقط نام فارسی معتبر ارائه کند.
- wrapper نباید translation اختراع کند؛ name ترجمه‌نشده با `null` نمایش داده می‌شود.
- `logo` در صورت unavailable بودن `null` است.
- `external_team_id: 0` canonical identity معتبر نیست.

## ۱۱. Endpoint جدول

### `GET /competitions/{competition_key}/seasons/{season_key}/standings`

این endpoint capability-dependent است.

```json
{
  "ok": true,
  "competition_key": "premier_league",
  "season_key": "2026-2027",
  "standings": [
    {
      "team_id": 501,
      "team_fa": "نام تیم",
      "team_en": null,
      "rank": 1,
      "played": 10,
      "wins": 7,
      "draws": 2,
      "losses": 1,
      "goals_for": 21,
      "goals_against": 8,
      "goal_difference": 13,
      "points": 23,
      "logo": null
    }
  ]
}
```

قواعد:

- `standings` همیشه array است.
- `team_id` باید با canonical team `id` همان competition/season سازگار باشد.
- فیلدهای آماری باید number یا در صورت unavailable بودن `null` باشند.
- اگر source جدول برای competition/season پیکربندی نشده یا provider آن را ارائه نکند، wrapper می‌تواند `404` یا `501` JSON برگرداند.
- شکست standings نباید availability سایر endpointها را کاهش دهد.
- ساختارهای grouped یا چندجدولی خارج از شکل تخت فعلی باید additive و versioned تعریف شوند.

## ۱۲. Endpoint زنده

### `GET /matches/{match_id}/live`

`match_id` همان Stable ID نرمال‌شده wrapper است.

```json
{
  "ok": true,
  "match": {
    "id": 75,
    "competition_key": "worldcup2026",
    "season_key": "2026",
    "provider": "varzesh3",
    "external_match_id": "441745",
    "home_team_id": 18,
    "away_team_id": 31,
    "kickoff_utc": "2026-06-29T01:00:00Z",
    "status": "live",
    "is_live": true,
    "live_phase": "second_half",
    "minute": 63,
    "home_score": 1,
    "away_score": 1,
    "status_title": "Live"
  }
}
```

قواعد:

- match object باید همان identity، scope، team، kickoff، status و score semantics endpoint season matches را استفاده کند.
- live response می‌تواند fieldهای Contract v1 مانند `raw_minute`, `live_badge`, penalty fields، `video_url` و `summary_url` را اضافه کند.
- نبود live update نباید باعث ساختن minute، score یا status شود.
- wrapper باید lookup داخلی از Stable ID به `external_match_id` را انجام دهد؛ MatchPulse نباید provider ID را به route بفرستد.

## ۱۳. Endpoint رویدادها

### `GET /matches/{match_id}/events`

```json
{
  "ok": true,
  "match_id": 75,
  "competition_key": "worldcup2026",
  "season_key": "2026",
  "provider": "varzesh3",
  "external_match_id": "441745",
  "events": [
    {
      "id": "2874946",
      "minute": 54,
      "raw_minute": "54",
      "raw_type": 1,
      "normalized_type": "goal",
      "label_fa": "گل",
      "label_en": "Goal",
      "is_scoring_event": true,
      "team_side": "home",
      "team_id": 18,
      "team_name": "Netherlands",
      "player": "Player Name",
      "assist": null,
      "description": null,
      "video_url": null
    }
  ]
}
```

قواعد:

- `events` همیشه array است، حتی وقتی event ثبت نشده باشد.
- provider event type باید پیش از پاسخ به `normalized_type` provider-independent تبدیل شود.
- eventهای مهم مانند goal، card، substitution و match eventها باید با semantics نرمال‌شده Contract v1 سازگار باشند.
- `team_side` یکی از `home`, `away` یا `null` است.
- `is_scoring_event` فقط برای scoring event قطعی `true` است.
- raw provider valueها مانند `raw_type` فقط metadata/debug هستند.
- Adapter اولیه Varzesh3 eventها را از `/livescore/football/matches/{external_match_id}/events` دریافت می‌کند.

## ۱۴. قوانین Pagination

Varzesh3 season endpointها response ریشه‌ای زیر دارند:

```json
{
  "hasPrev": false,
  "hasMore": true,
  "_links": [],
  "items": []
}
```

Matchها مستقیماً در `items` نیستند و از مسیر زیر استخراج می‌شوند:

```text
items[].dates[].matches[]
```

قواعد Adapter:

- pagination باید بر اساس valueهای provider `_links` دنبال شود.
- wrapper نباید page size ثابت فرض کند.
- wrapper نباید `skip` increment اختراع کند.
- loop termination باید بر اساس link/availability واقعی provider و guard ایمنی انجام شود.
- recordهای جمع‌آوری‌شده از pageها و discovery windowهای مختلف باید پیش از normalization با provider match ID deduplicate شوند.
- order نهایی باید deterministic باشد؛ pagination نباید ترتیب یک response ثابت را تصادفی کند.
- Contract v2 در این نسخه pagination provider را به MatchPulse core افشا نمی‌کند. اضافه‌شدن public pagination باید additive و versioned باشد.

## ۱۵. قوانین Time و Timezone

- `kickoff_utc` زمان canonical مسابقه و ISO 8601 UTC است.
- مقدار provider مانند `0001-01-01T00:00:00` نامعتبر است و هرگز نباید به‌عنوان `kickoff_utc` منتشر شود.
- season endpointهای Varzesh3 منبع قابل اتکای همیشگی برای UTC kickoff دقیق نیستند.
- زمان دقیق باید از field معتبر provider مانند Varzesh3 livescore `startOnUtc` گرفته شود.
- اگر زمان دقیق قابل resolve نیست، `kickoff_utc` باید `null` باشد و warning مناسب می‌تواند اضافه شود.
- wrapper نباید local time یا server timezone را به‌عنوان UTC برچسب بزند.
- localized convenience fieldهای Contract v1 مانند `date_iran`, `time_iran` و `datetime_iran` optional هستند و جای `kickoff_utc` را نمی‌گیرند.
- تبدیل timezone در wrapper انجام می‌شود و MatchPulse نباید مقدار canonical را دوباره تبدیل کند.

## ۱۶. نرمال‌سازی Status و Live Phase

statusهای canonical Contract v2 فقط عبارت‌اند از:

- `upcoming`
- `live`
- `finished`

Match phaseها باید در `live_phase` قرار گیرند، نه `status`. نمونه‌ها:

- `first_half`
- `halftime`
- `second_half`
- `extra_time`
- `penalties`

قواعد:

- `status` باید provider-independent باشد.
- `is_live` برای `status: "live"` برابر `true` و برای `upcoming` یا `finished` برابر `false` است.
- halftime، extra time و penalties در حال اجرا همچنان `status: "live"` دارند.
- raw statusهای مشاهده‌شده Varzesh3 شامل `1` برای upcoming، `2` برای یک live state و `7` برای finished هستند.
- این raw valueها provider-specific هستند و MatchPulse فقط normalized status را مصرف می‌کند.
- `pending_result` یک state مشتق‌شده در application layer MatchPulse است و status الزامی wrapper در Contract v2 نیست.
- نبود `liveTime`، minute یا live list record به‌تنهایی اثبات finished بودن نیست.

## ۱۷. مسئولیت‌های Provider Adapter

Provider Adapter مرز تمام رفتار provider-specific است. برای Adapter اولیه Varzesh3، endpointهای مشاهده‌شده عبارت‌اند از:

```text
/football/leagues/{league_id}/seasons/{season_id}/matches
/football/leagues/{league_id}/seasons/{season_id}/fixtures?skip={offset}
/football/leagues/{league_id}/seasons/{season_id}/results?skip={offset}
/football/leagues/{league_id}/seasons/{season_id}/standing
/livescore/football/matches/{external_match_id}/events
```

Varzesh3 livescore endpointها داده نزدیک به تاریخ را شامل fieldهای زیر ارائه می‌کنند:

- league id و title
- match id
- `startOnUtc`
- `status`
- `statusTitle`
- `isLive`
- `liveTime`
- goals
- host
- guest
- event linkها

مسئولیت Adapter:

- authentication و secret management
- mapping `league_id` و `season_id` به `competition_key` و `season_key`
- پیمایش structure تو در توی `items[].dates[].matches[]`
- دنبال‌کردن provider `_links` برای pagination
- deduplication با provider match ID
- recovery امن team identity و جلوگیری از canonical ID صفر
- resolve کردن `kickoff_utc` از source قابل اعتماد
- normalize کردن raw status به `upcoming`, `live`, `finished`
- normalize کردن match phase در `live_phase`
- normalize کردن event typeها پیش از پاسخ به MatchPulse
- مدیریت cache، polling، retry، backoff و rate limit
- جدا نگه‌داشتن raw provider payload و enumها از MatchPulse core

## ۱۸. رفتار Missing و Unresolved Data

- optional value ناموجود باید `null` باشد، نه مقدار ساخته‌شده.
- arrayهای `competitions`, `seasons`, `matches`, `teams`, `standings` و `events` باید در پاسخ موفق همیشه array باشند.
- wrapper نباید translation اختراع کند؛ برای نمونه `name_en` در صورت نبود ترجمه معتبر `null` است.
- `kickoff_utc` نامعتبر یا sentinel باید `null` شود.
- score ناموجود `null` است و score صفر معتبر باقی می‌ماند.
- اگر team identity resolve نشود، wrapper نباید `0`، hash موقت یا counter ناپایدار را canonical ID اعلام کند.
- unresolved identity باید با warning یا state صریح گزارش شود و field شناسه unresolved می‌تواند `null` باشد.
- داده cached معتبر نباید به دلیل timeout یا response خالی موقت با داده خالی جایگزین شود.
- نبود standings یک failure محدود به capability است و نباید سایر داده‌ها را حذف کند.
- wrapper نباید unavailable provider را با fabricated data پنهان کند.

## ۱۹. Caching، Polling و Rate Limit

- Generic Wrapper باید cache را بر اساس competition، season، endpoint و entity scope جدا کند.
- schedule، teams و archived results می‌توانند TTL طولانی‌تری از live و events داشته باشند.
- polling live باید فقط برای windowها و matchهای مرتبط انجام شود.
- یک match دیده‌شده در چند polling window باید با provider match ID deduplicate شود.
- retry باید محدود و همراه backoff باشد.
- rate-limit handling داخل Provider Adapter انجام می‌شود؛ MatchPulse نباید quota provider را بداند.
- stale-data fallback در outage کوتاه مجاز است، به شرطی که با fieldی مانند `stale: true` یا warning آشکار شود.
- cache خالی ناشی از timeout نباید cache غیرخالی معتبر را overwrite کند.
- polling و refresh نباید Stable IDها را تغییر دهند.

## ۲۰. رفتار Error

Contract v2 یک error schema سخت و کامل تعریف نمی‌کند، اما این اصول الزامی‌اند:

- استفاده از HTTP status code معتبر.
- پاسخ error باید UTF-8 JSON باشد؛ HTML error page مجاز نیست.
- competition ناشناخته باید با client error مناسب گزارش شود.
- season ناشناخته باید از data-source unavailable قابل تشخیص باشد.
- capability پشتیبانی‌نشده مانند standings می‌تواند `404` یا `501` برگرداند.
- `warning`, `error` و `stale` می‌توانند به‌صورت additive در response حضور داشته باشند.
- provider timeout یا failure نباید response موفق fabricated تولید کند.
- token، credential، raw authorization header و secret نباید در response یا log ظاهر شوند.

نمونه غیرالزام‌آور:

```json
{
  "ok": false,
  "error": "Competition season data source not configured"
}
```

## ۲۱. Backward Compatibility و Versioning

- Contract v1 و wrapper `worldcup2026` بدون تغییر معتبر می‌مانند.
- Contract v2 برای Generic Football Wrapper آینده است.
- اضافه‌کردن field optional بدون تغییر semantics موجود backward-compatible است.
- حذف required field، تغییر data type، تغییر Stable ID semantics، تغییر canonical status یا تغییر root shape breaking change است.
- breaking change به contract version جدید نیاز دارد.
- grouped standings، multi-table standings و public pagination باید additive و versioned باشند.
- Provider Adapter جدید نباید MatchPulse را مجبور به استفاده از provider-specific logic کند.
- migration باید مرحله‌ای باشد و امکان اجرای هم‌زمان v1 و v2 را حفظ کند.

## ۲۲. Checklist اتصال Generic Wrapper

- [ ] معماری `MatchPulse -> Competition Data Dispatcher -> Generic Football Wrapper -> Provider Adapter -> External Provider` رعایت شده است.
- [ ] `GET /competitions` competition registry پایدار برمی‌گرداند.
- [ ] `GET /competitions/{competition_key}/seasons` season registry پایدار برمی‌گرداند.
- [ ] endpointهای season-scoped matches و teams پیاده‌سازی شده‌اند.
- [ ] standings فقط با capability واقعی فعال است.
- [ ] live و events با Stable Match ID قابل دریافت‌اند.
- [ ] هر match شامل `competition_key` و `season_key` است.
- [ ] هر team شامل `competition_key` و `season_key` است.
- [ ] `id`ها canonical و مستقل از provider business identity هستند.
- [ ] provider `league_id` و `season_id` فقط Adapter metadata هستند.
- [ ] `external_match_id` و `external_team_id` برای tracing/mapping استفاده می‌شوند.
- [ ] team ID صفر هرگز canonical نمی‌شود.
- [ ] unresolved team identity صریح گزارش می‌شود و ID جعلی ساخته نمی‌شود.
- [ ] provider pagination بر اساس `_links` دنبال می‌شود.
- [ ] fixed page size یا skip increment فرض نشده است.
- [ ] matchهای تکراری با provider match ID deduplicate می‌شوند.
- [ ] `0001-01-01T00:00:00` به‌عنوان `kickoff_utc` منتشر نمی‌شود.
- [ ] kickoff دقیق از source معتبر مانند `startOnUtc` resolve می‌شود.
- [ ] statusها فقط `upcoming`, `live`, `finished` هستند.
- [ ] phaseهایی مانند halftime، extra time و penalties در `live_phase` هستند.
- [ ] event typeها پیش از رسیدن به MatchPulse normalize می‌شوند.
- [ ] arrayها حتی در حالت empty همچنان array هستند.
- [ ] translation ساخته نمی‌شود و مقدار unavailable برابر `null` است.
- [ ] caching، stale fallback، polling، retry و rate-limit handling تست شده‌اند.
- [ ] خطاها JSON هستند و secretها افشا نمی‌شوند.
- [ ] local و server contract testهای یکسان را پاس می‌کنند.
- [ ] Contract v1 و wrapper فعلی `worldcup2026` بدون تغییر باقی مانده‌اند.

## ۲۳. یافته‌های اولیه انطباق Varzesh3

یافته‌های زیر observations اولیه برای ساخت Adapter هستند و universal contract requirement محسوب نمی‌شوند:

- season match endpointهای مشاهده‌شده شامل `matches`, `fixtures`, `results` و `standing` در scope `league_id` و `season_id` هستند.
- root پاسخ season match list شامل `hasPrev`, `hasMore`, `_links`, `items` است.
- matchها در `items[].dates[].matches[]` قرار دارند.
- pagination باید provider `_links` را دنبال کند و skip ثابت قابل فرض نیست.
- fixtures ممکن است `host.id` و `guest.id` را `0` برگرداند؛ Adapter به identity recovery نیاز دارد.
- standings برای همه competitionها یا phaseها یکسان در دسترس نیست و ممکن است `404` برگرداند.
- season endpointها ممکن است `utcTime: "0001-01-01T00:00:00"` داشته باشند که برای `kickoff_utc` نامعتبر است.
- livescore داده نزدیک به تاریخ شامل league، match، `startOnUtc`، raw status، `statusTitle`، `isLive`، `liveTime`، goals، host، guest و event linkها ارائه می‌کند.
- raw statusهای مشاهده‌شده `1`, `2`, `7` به‌ترتیب با upcoming، یک live state و finished نگاشت می‌شوند، اما فقط Adapter باید این mapping را بداند.
- eventها از endpoint جداگانه `/livescore/football/matches/{external_match_id}/events` دریافت می‌شوند.
- match ممکن است در چند discovery window دیده شود و باید پیش از normalization deduplicate شود.
- provider `league_id` و `season_id` باید در Adapter map شوند و نباید به business identifiers در MatchPulse تبدیل شوند.

این یافته‌ها برای شروع Adapter اولیه Varzesh3 کافی‌اند، اما compliance نهایی فقط با contract testهای endpoint، identity، time، status، pagination، missing data و failure behavior تأیید می‌شود.
