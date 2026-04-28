# SilverquiLLM-bench

Notion-to-repo spec sync tooling.

## sync_notion_specs.py

Exports Notion spec pages to markdown files in a repo:

- `AGENTS.md` (child of project root) -> `./AGENTS.md`
- `Specs/*` (children of the Specs page) -> `./docs/specs/<page_title>.md`

### Prerequisites

```bash
pip install requests
```

### Usage

```bash
# Set your Notion integration token
export NOTION_TOKEN=ntn_...

# Run the sync
python sync_notion_specs.py --project-root-id <PAGE_ID> --output-dir ./
```

### Getting a Notion token

1. Go to https://www.notion.so/profile/integrations
2. Create a new internal integration with **Read content** capability
3. Connect the integration to your project pages (page menu -> Connections)

### Getting the project root page ID

Open the project page in your browser. The page ID is the last 32 hex characters of the URL:

```
https://www.notion.so/My-Project-abc123def456789012345678abcdef12
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

Format as UUID: `abc123de-f456-7890-1234-5678abcdef12`

### Auto-commit wrapper

```bash
chmod +x sync_and_commit.sh
./sync_and_commit.sh <PROJECT_ROOT_ID>
```

Syncs specs and commits + pushes if anything changed.

## Expected Notion structure

```
Project Page
+-- AGENTS.md          -> exported to ./AGENTS.md
+-- Specs/
|   +-- ARCHITECTURE.md  -> exported to ./docs/specs/ARCHITECTURE.md
|   +-- DATA-STORES.md   -> exported to ./docs/specs/DATA-STORES.md
|   +-- ...
+-- (other pages, ignored)
```
