document.addEventListener("DOMContentLoaded", function () {
  // Trova il fieldset Appartenenze cercando nell'h2
  var fieldsets = document.querySelectorAll("fieldset");
  var target = null;
  fieldsets.forEach(function (fs) {
    var h2 = fs.querySelector("h2");
    if (h2 && h2.textContent.indexOf("Appartenenze") !== -1) {
      target = fs;
    }
  });
  if (!target) return;

  // Trova l'ultimo inline-group (Denominazioni precedenti / comuni soppressi)
  var inlineGroups = document.querySelectorAll(".inline-group");
  var lastInline = inlineGroups[inlineGroups.length - 1];
  if (lastInline) {
    lastInline.parentNode.insertBefore(target, lastInline.nextSibling);
  }
});
