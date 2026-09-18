# Pelican explorer

Builds a self-contained interactive fragment from the retained research records 0101, 0102, 0436, 0038 and Bonsai2 rerun 0202. These recorded datasets are local artifacts, not included in the repository.

```sh
python3 scripts/research/pelican-explorer/build.py --records-root /path/to/research-records --output /path/to/pelican-lab.html
```

The explorer compares original drawings, token neighborhoods, measured RMS from layers 0/31/63, and checkpoint recipes. Relative sequence positions are not aligned semantics or elapsed time. The optional repair changes exactly the known duplicate y2 attribute to y1 for illustration; it never modifies original output or activation records. The fragment uses the Codex visualization theme utilities. The visualization skill render.py can wrap it for standalone preview.
