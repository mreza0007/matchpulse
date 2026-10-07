const PATHS = {
  clock: "M12 8v4l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  stadium: "M3 10l9-6 9 6v10H3z M3 10h18 M7 20v-6h10v6",
  location: "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0 M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4",
  trophy: "M8 3h8v8a4 4 0 0 1-8 0z M8 5H4v3a4 4 0 0 0 4 4 M16 5h4v3a4 4 0 0 1-4 4 M12 15v6 M8 21h8",
  home: "M3 11l9-8 9 8 M5 9v12h14V9 M9 21v-8h6v8",
  live: "M5 12h2l3-6 4 12 3-6h2",
  news: "M5 3h14v18H5z M8 7h8 M8 11h8 M8 15h4 M8 18h8",
  check: "M5 12l4 4L19 6",
};

export default function UiIcon({ name }) {
  return (
    <svg className="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={PATHS[name] || PATHS.trophy} />
    </svg>
  );
}
