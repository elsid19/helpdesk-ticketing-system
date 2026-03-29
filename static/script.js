// Simple client-side row highlighting helper for quick demo UX.
document.addEventListener("DOMContentLoaded", () => {
  const rows = document.querySelectorAll("#ticketsTable tbody tr");
  rows.forEach((row) => {
    row.addEventListener("mouseenter", () => {
      row.style.backgroundColor = "#f8fafc";
    });
    row.addEventListener("mouseleave", () => {
      row.style.backgroundColor = "";
    });
  });
});
