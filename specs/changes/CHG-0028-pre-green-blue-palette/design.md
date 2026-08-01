---
kind: design-delta
id: CHG-0028-DESIGN
status: in_progress
target: 0.1
---

# Design decisions

1. Use the earlier captured indigo conversation as the source of truth: `#5667d8` for primary
   action, `#4c82c9` for informational activity, `#f7f8fc` for the canvas, and `#ffffff` for the main
   reading surface.
2. Keep success/healthy green (`#2f966c`) semantic and localized to status indicators.
3. Keep one source-of-truth palette in the existing CHG-0025/0027 surface blocks; do not append
   another late override layer that can drift from the captured conversation.
4. Keep the CHG-0027 conversation hierarchy unchanged: white transcript, quiet activity, compact
   composer, and secondary Task Monitor/Trace surfaces.
