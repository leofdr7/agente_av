export default function Link({ href, children, ...props }) {
  const target = new URL(typeof href === "string" ? href : href.pathname, window.location.origin);
  if (new URLSearchParams(window.location.search).get("theme") === "dark") target.searchParams.set("theme", "dark");
  return <a href={`${target.pathname}${target.search}`} {...props}>{children}</a>;
}
