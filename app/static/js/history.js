/**
 * Nutri Milk Guard - History Page Search & Filter Controller.
 */

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("history-search");
  const table = document.getElementById("history-table");

  if (!searchInput || !table) return;

  const rows = table.querySelectorAll("tbody tr");

  searchInput.addEventListener("input", (e) => {
    const query = e.target.value.toLowerCase().trim();

    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      if (text.includes(query)) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });
  });
});
