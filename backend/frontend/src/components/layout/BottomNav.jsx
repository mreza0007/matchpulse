import UiIcon from "./UiIcon.jsx";

const NAV_ITEMS = [
  { key: "home", icon: "home", label: "home" },
  { key: "live", icon: "live", label: "live" },
  { key: "competitions", icon: "trophy", label: "competitionsPage" },
  { key: "news", icon: "news", label: "news" },
  { key: "predictions", icon: "check", label: "prediction" },
];

export default function BottomNav({ activeTab, onChange, t, lang }) {
  return (
    <nav className="bottom-nav" aria-label={lang === "fa" ? "ناوبری اصلی" : "Main navigation"}>
      {NAV_ITEMS.map((item) => (
        <button
          aria-current={activeTab === item.key ? "page" : undefined}
          className={activeTab === item.key ? "active" : ""}
          key={item.key}
          onClick={() => onChange(item.key)}
          type="button"
        >
          <span aria-hidden="true"><UiIcon name={item.icon} /></span>
          <small>{t[item.label]}</small>
        </button>
      ))}
    </nav>
  );
}
