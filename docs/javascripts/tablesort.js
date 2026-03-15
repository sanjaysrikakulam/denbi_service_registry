document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("article table:not([class])").forEach(function (table) {
    new Tablesort(table);
  });
});
