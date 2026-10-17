// ЛР9 · Крок 1. Проєкція графа в пам'ять GDS (потрібен плагін Graph Data Science).
// Усі вузли й усі типи зв'язків, орієнтація UNDIRECTED: для «важливості» знань і спільнот
// напрям зв'язку (хто на кого посилається) не важливий — важлива зв'язність.
CALL gds.graph.drop('energy', false) YIELD graphName;
CALL gds.graph.project('energy', '*', {ALL: {type: '*', orientation: 'UNDIRECTED'}})
YIELD graphName, nodeCount, relationshipCount;

