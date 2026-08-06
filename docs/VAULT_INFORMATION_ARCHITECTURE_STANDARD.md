# Vault Information Architecture Standard

The maintained vault is a narrative navigation surface. Canonical narrative documents live only under `Project_Obsidian_Vault/00_Canonical/`; machine registries live in `configs/` and are linked by reference rather than copied into prose. Every managed note has exactly one registered parent except the root MOC. Links are path-qualified, transclusions are prohibited, generated breadcrumbs are owned only by the maintainer, and oversized notes are diagnostics rather than automatic split targets.

Run `vault_maintainer.py report`, `check`, then `sync-navigation` dry-run before `sync-navigation --apply`. The tool fails closed when registry, parentage, links, or non-generated content are unsafe.
