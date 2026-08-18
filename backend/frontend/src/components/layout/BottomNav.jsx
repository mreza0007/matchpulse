const NAV_ITEMS = [
  { key: "home", icon: "⌂", label: "خانه" },
  { key: "live", icon: "●", label: "زنده" },
  { key: "competitions", icon: "⚽", label: "مسابقات" },
  { key: "news", icon: "▤", label: "اخبار" },
  { key: "predictions", icon: "✓", label: "پیش‌بینی" },
];

export default function BottomNav({ activeTab, onChange }) {
  return (
    <nav className="bottom-nav" aria-label="ناوبری اصلی">
      {NAV_ITEMS.map((item) => (
        <button
          aria-current={activeTab === item.key ? "page" : undefined}
          className={activeTab === item.key ? "active" : ""}
          key={item.key}
          onClick={() => onChange(item.key)}
          type="button"
        >
          <span aria-hidden="true">{item.icon}</span>
          <small>{item.label}</small>
        </button>
      ))}
    </nav>
  );
}
