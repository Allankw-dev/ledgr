/** First tab stop on pages with a menu: lets keyboard and screen-reader users jump past it to the page content. */
export function SkipLink() {
  return (
    <a
      href="#main-content"
      onClick={(e) => {
        // The router's <BrowserRouter> would treat a bare #hash as navigation; focus the target ourselves instead.
        const target = document.getElementById('main-content');
        if (target) {
          e.preventDefault();
          target.focus();
          target.scrollIntoView();
        }
      }}
      className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:rounded-lg focus:bg-green focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-ink-950"
    >
      Skip to main content
    </a>
  );
}
