"""Second-brain layer: consolidation, windowing, retrieval, and serving.

Built on the core pipeline (sources/, scraper, store) and the findings of
the date-windowing study (experiments/date_windowing/FINDINGS.md) and the
topic-relation study (output/second-brain-tests/README.md):

- windowing:   H1 sliding windows, static 14-day magnitude (study winner)
- consolidate: batch re-clustering of the live corpus (vectors for edges,
               top-terms for labels), with an append-only change log
- retrieval:   cosine search over stored document vectors, URL-cited
- serve:       digest/timeline/search endpoints + static site builder
"""
