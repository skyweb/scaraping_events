/**
 * Aggiunge classe row-inactive alle righe con chip "Inattivo" (sfondo rosso leggero).
 */
document.addEventListener('DOMContentLoaded', function() {
    var rows = document.querySelectorAll('#result_list tbody tr, #changelist table tbody tr, .results table tbody tr');
    rows.forEach(function(row) {
        if (row.textContent.includes('Inattivo')) {
            row.classList.add('row-inactive');
        }
    });
});
