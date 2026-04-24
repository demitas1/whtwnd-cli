# whtwnd-cli

English | [日本語](README.ja.md)

A Python CLI tool for posting Markdown articles to [WhiteWind](https://whtwnd.com) (whtwnd.com). Also supports posting skeets to Bluesky.

WhiteWind is a Markdown blog service built on AT Protocol (the same protocol as Bluesky). Articles are stored on your own Bluesky PDS and fully owned by you.

## Features

**WhiteWind posting (`whtwnd_post.py`)**

- Post, update, and delete articles from Markdown files
- Automatic local image upload & URL replacement
- Visibility control (public / URL-only / author-only / draft)
- Automatic title extraction from Markdown H1
- Search, update, and delete articles by title
- List posted articles

**Bluesky posting (`bsky_post.py`)**

- Post skeets (text and images, up to 4)
- Automatic rich-text detection (URLs, mentions, hashtags)
- Language tag support

## Setup

### 1. Clone the repository and install dependencies

```bash
git clone https://github.com/demitas1/whtwnd-cli.git
cd whtwnd-cli
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

Generate a [Bluesky app password](https://bsky.app/settings/app-passwords), then create a config file.

**In your home directory (recommended):**

```bash
cat > ~/.bsky_config.json << 'EOF'
{
  "handle": "yourname.bsky.social",
  "password": "xxxx-xxxx-xxxx-xxxx"
}
EOF
chmod 600 ~/.bsky_config.json
```

**In the project directory:**

```bash
cat > .bsky_config.json << 'EOF'
{
  "handle": "yourname.bsky.social",
  "password": "xxxx-xxxx-xxxx-xxxx"
}
EOF
```

> **Note:** Use an **app password**, not your main Bluesky password. If placed in the project directory, it is excluded from Git tracking via `.gitignore`.

The config file in the current directory takes priority. If not found, `~/.bsky_config.json` is used.

## Usage — WhiteWind

Run the following commands with the `venv` environment activated, or from the project directory.

### Post an article

```bash
# Auto-extract title from Markdown H1 and publish publicly
python whtwnd_post.py post article.md

# Specify title explicitly
python whtwnd_post.py post article.md --title "Article Title"

# Save as draft (visible to yourself only)
python whtwnd_post.py post article.md --draft

# Visible only to those with the URL
python whtwnd_post.py post article.md --visibility url

# Skip image upload
python whtwnd_post.py post article.md --no-images
```

**Visibility options (`--visibility`):**

| Value | Description |
|---|---|
| `public` | Publicly visible (default) |
| `url` | Visible only to those with the URL |
| `author` | Visible to yourself only |

`--draft` is equivalent to `--visibility author`.

### Update an article

```bash
# Update by title
python whtwnd_post.py update --title "Existing Article Title" new_article.md

# Update by rkey (article ID)
python whtwnd_post.py update 3la5v2sq4s42q new_article.md

# Update by AT URI
python whtwnd_post.py update at://did:plc:.../com.whtwnd.blog.entry/3la5v2sq4s42q new_article.md

# Update by WhiteWind article URL (paste directly from browser)
python whtwnd_post.py update https://whtwnd.com/yourname.bsky.social/3la5v2sq4s42q new_article.md

# Also change the title
python whtwnd_post.py update --title "Old Title" new_article.md --new-title "New Title"
```

### Delete an article

```bash
# Delete by title (confirmation prompt shown)
python whtwnd_post.py delete --title "Article Title"

# Delete by rkey
python whtwnd_post.py delete 3la5v2sq4s42q

# Delete by WhiteWind article URL (paste directly from browser)
python whtwnd_post.py delete https://whtwnd.com/yourname.bsky.social/3la5v2sq4s42q

# Skip confirmation prompt
python whtwnd_post.py delete --title "Article Title" --yes
```

The confirmation prompt shows the title, rkey, and AT URI before deleting:

```
The following article will be deleted:
  Title: My Article
  rkey: 3la5v2sq4s42q
  AT URI: at://did:plc:.../com.whtwnd.blog.entry/3la5v2sq4s42q
Proceed with deletion? [y/N]:
```

### List articles

```bash
python whtwnd_post.py list
```

Example output:

```
────────────────────────────────────────────────────────────
Title                          Visibility   Created
────────────────────────────────────────────────────────────
My Blog Post                   public       2026-02-19  (3mf6kmdywdz2q)
────────────────────────────────────────────────────────────
```

### Image paths in Markdown

Simply write the relative path to a local image file — it will be uploaded automatically.

```markdown
# Article Title

Body text...

![Caption](./images/screenshot.png)
![Figure 1](../assets/fig1.jpg)
```

Images are automatically uploaded to your PDS and the URLs are replaced in the content.
URLs starting with `https://` or `http://` are used as-is.

**Note on image path resolution:**

Relative image paths are resolved relative to **the directory containing the Markdown file**, not the current working directory where you run the command.

```
Example: python whtwnd_post.py post path/to/article.md
```

| Written in article.md | Resolved path |
|---|---|
| `![](./image.png)` | `path/to/image.png` |
| `![](images/fig1.jpg)` | `path/to/images/fig1.jpg` |
| `![](../shared/img.png)` | `path/shared/img.png` |

As long as the relative positions of the Markdown file and image files are correct, the tool works regardless of which directory you run the command from.

## Usage — Bluesky

### Post a skeet

```bash
# Specify text directly
python bsky_post.py post "Great weather today #bluesky"

# Read from file
python bsky_post.py post --file message.txt

# Read from stdin
echo "Test post" | python bsky_post.py post --file -

# With images (up to 4)
python bsky_post.py post "Posted a photo" --image photo.jpg

# Multiple images with language tags
python bsky_post.py post "Test" --image a.jpg --image b.jpg --lang ja --lang en
```

**Rich text (auto-detected):**

| Pattern | Result |
|---|---|
| `https://...` | Clickable link |
| `@handle.domain` | Mention link |
| `#hashtag` | Tag link |

## License

MIT
