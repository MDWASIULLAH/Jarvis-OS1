"use client";
/**
 * For subsystems that genuinely have no manager in this build.
 *
 * The old version stamped "Unavailable" beside every listed item, which read as
 * "this is broken" rather than "this was never shipped". It states the fact once
 * and lists the scope as plain text.
 */
export function DomainUnavailable({ title, description, items }: { title: string; description: string; items: string[] }) {
  return <section className="operations-card domain-unavailable">
    <h2>{title}</h2>
    <p>{description}</p>
    <ul>{items.map(item => <li key={item}>{item}</li>)}</ul>
  </section>;
}
