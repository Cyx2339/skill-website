#!/usr/bin/env python3
"""Render a self-contained personal website from the public site data."""

import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
from shutil import copyfile
from string import Template
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit


ASSETS = Path(__file__).resolve().parent.parent / "assets"
IMAGE_TYPES = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
SECTIONS = ("projects", "strengths", "experience", "skills", "education", "contact")
LABELS = {
    "zh": {
        "projects": "精选项目", "experience": "工作经历", "education": "教育经历",
        "skills": "专业能力", "contact": "联系", "detail": "查看项目",
        "back": "返回项目", "skip": "跳到正文", "resume": "下载简历",
        "strengths": "个人优势", "home": "首页", "top": "回到顶部", "nav": "站点导航",
        "view_projects": "查看项目", "featured_detail": "查看案例", "row_detail": "查看详情",
        "status": "项目状态", "flow": "项目流程",
    },
    "en": {
        "projects": "Selected work", "experience": "Experience", "education": "Education",
        "skills": "Skills", "contact": "Contact", "detail": "View project",
        "back": "Back to projects", "skip": "Skip to content", "resume": "Download résumé",
        "strengths": "Strengths", "home": "Home", "top": "Back to top", "nav": "Site navigation",
        "view_projects": "View selected work", "featured_detail": "View case study",
        "row_detail": "View details", "status": "Project status", "flow": "Project workflow",
    },
}


def text(value):
    return escape(str(value), quote=True)


def paragraphs(value):
    entries = [value] if isinstance(value, str) else value or []
    return "".join(f"<p>{text(entry)}</p>" for entry in entries if entry)


def link(url, label, attributes=""):
    return f'<a href="{text(url)}"{attributes}>{text(label)}</a>'


def public_url(value, contact=False):
    if not isinstance(value, str) or any(char.isspace() for char in value):
        raise ValueError("A public URL must be a string with no whitespace.")
    parts = urlsplit(value)
    if parts.scheme in {"http", "https"} and parts.hostname:
        return value
    if contact and parts.scheme in {"mailto", "tel"} and parts.path:
        return value
    raise ValueError("Use an absolute http or https URL, or mailto/tel for a contact link.")


def tags(items):
    if not items:
        return ""
    return '<ul class="tags">' + "".join(f"<li>{text(item)}</li>" for item in items) + "</ul>"


def metadata(*values):
    return " · ".join(text(value) for value in values if value)


def text_link(url, label, arrow, extra_class="", aria_label=""):
    direction = f'<span class="link-arrow" aria-hidden="true">{arrow}</span>'
    content = f"{direction} {text(label)}" if arrow == "←" else f"{text(label)} {direction}"
    classes = "text-link" + (" " + extra_class if extra_class else "")
    aria = f' aria-label="{text(aria_label)}"' if aria_label else ""
    return f'<a href="{text(url)}" class="{classes}"{aria}>{content}</a>'


def section(key, label, content):
    if not content:
        return ""
    return (
        f'<section class="section" id="{key}" aria-labelledby="{key}-title">\n'
        f'  <h2 id="{key}-title">{text(label)}</h2>\n{content}\n</section>'
    )


def timeline(items):
    rows = []
    for item in items:
        date = metadata(item.get("period"), item.get("location"))
        date_block = f'<p class="metadata">{date}</p>' if date else "<div></div>"
        subtitle = f'<p class="metadata">{text(item["subtitle"])}</p>' if item.get("subtitle") else ""
        summary = paragraphs(item.get("summary"))
        prose = f'<div class="entry-summary">{summary}</div>' if summary else ""
        rows.append(
            f'<article class="fact-row">{date_block}'
            f'<div><h3>{text(item["title"])}</h3>{subtitle}{prose}</div></article>'
        )
    return "\n".join(rows)


def fact_list(items):
    if not items:
        return ""
    rows = [
        f'<div class="fact-row"><dt>{text(item["title"])}</dt>'
        f'<dd>{paragraphs(item["summary"])}</dd></div>'
        for item in items
    ]
    return '<dl class="fact-list">\n' + "\n".join(rows) + "\n</dl>"


class Site:
    def __init__(self, data, source_dir, destination, styles):
        self.data = data
        self.source_dir = source_dir
        self.destination = destination
        self.styles = styles
        self.images = {}
        self.name = data["name"].strip()
        if not self.name:
            raise ValueError('Provide a nonempty "name".')
        self.headline = (data.get("headline") or "").strip()
        self.language = data.get("language") or "zh-CN"
        language_key = "zh" if self.language.lower().startswith("zh") else "en"
        overrides = data.get("labels") or {}
        self.labels = dict(LABELS[language_key])
        if "detail" in overrides:
            self.labels.update(featured_detail=overrides["detail"], row_detail=overrides["detail"])
        self.labels.update(overrides)
        self.template = Template((ASSETS / "page.html").read_text(encoding="utf-8"))
        self.contact_links = [
            link(public_url(item["url"], contact=True), item["label"])
            for item in data.get("links", [])
        ]
        self.projects = data.get("projects", [])
        self.project_pages = {}
        self.animate_flow = bool(self.projects and self.projects[0].get("process"))
        requested_order = data.get("section_order", [])
        if any(key not in SECTIONS for key in requested_order):
            raise ValueError("section_order contains an unknown section.")
        self.section_order = tuple(dict.fromkeys([*requested_order, *SECTIONS]))

    def copy_media(self, source_value, allowed_extensions, name):
        source = (self.source_dir / source_value).resolve(strict=True)
        if not source.is_file() or source.suffix.lower() not in allowed_extensions:
            raise ValueError(f"Unsupported media file type: {source.suffix or '(none)'}")
        path = self.destination / "media" / (name + source.suffix.lower())
        path.parent.mkdir(exist_ok=True)
        copyfile(source, path)
        return path.relative_to(self.destination).as_posix()

    def figure(self, media, class_name, eager=False):
        if not media:
            return ""
        file = media["file"]
        source = (self.source_dir / file).resolve()
        if source not in self.images:
            self.images[source] = self.copy_media(file, IMAGE_TYPES, f"image-{len(self.images) + 1}")
        loading = "" if eager else ' loading="lazy"'
        image = f'<img src="{self.images[source]}" alt="{text(media.get("alt", ""))}"{loading}>'
        caption = media.get("caption")
        label = f"<figcaption>{text(caption)}</figcaption>" if caption else ""
        return f'<figure class="{class_name}">{image}{label}</figure>'

    def build(self):
        copyfile(ASSETS / "site.css", self.destination / "site.css")
        if self.styles:
            copyfile(self.styles, self.destination / "custom.css")
        if self.animate_flow:
            copyfile(ASSETS / "site.js", self.destination / "site.js")

        self.resume = self.copy_media(self.data["resume"], {".pdf"}, "public-resume") if self.data.get("resume") else ""
        nav_content = {
            "projects": self.projects,
            "strengths": self.data.get("strengths"),
            "experience": self.data.get("experience"),
            "contact": self.contact_links,
        }
        self.nav_items = {
            key: self.labels[key]
            for key in self.section_order
            if nav_content.get(key)
        }

        seen_ids = set()
        for index, project in enumerate(self.projects):
            if not any(project.get(key) for key in ("sections", "gallery", "process")):
                continue
            fallback = sha256(project["title"].encode()).hexdigest()[:10]
            slug = project.get("id") or fallback
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or len(slug) > 64:
                raise ValueError("A project id must use up to 64 lowercase ASCII letters, digits and hyphens.")
            base = slug
            serial = 2
            while slug in seen_ids:
                slug = f"{base}-{serial}"
                serial += 1
            seen_ids.add(slug)
            self.project_pages[index] = f"project-{slug}.html"

        self.write_page("index.html", self.home())
        for index, filename in self.project_pages.items():
            project = self.projects[index]
            self.write_page(filename, self.detail(project, featured=index == 0), project["title"], project.get("summary", ""))

    def write_page(self, filename, main, page_title="", description=""):
        is_home = filename == "index.html"
        prefix = "" if is_home else "index.html"
        nav = [link(f"{prefix}#{key}", title) for key, title in self.nav_items.items()]
        if self.resume:
            nav.append(link(self.resume, self.labels["resume"], ' class="resume-link" download'))
        navigation = ""
        if nav:
            nav_label = text(self.labels["nav"])
            navigation = f'<nav class="site-nav" aria-label="{nav_label}">' + "".join(nav) + "</nav>"
        home_attrs = ' class="home-link" aria-current="page"' if is_home else ' class="home-link"'
        home_link = link("#top" if is_home else "index.html", self.labels["home"], home_attrs)
        footer_links = self.contacts() if not is_home else ""
        custom = '<link rel="stylesheet" href="custom.css">\n  ' if self.styles else ""
        script = '<script src="site.js" defer></script>' if is_home and self.animate_flow else ""
        title_parts = (self.name, self.headline) if is_home else (page_title, self.name)
        title = " · ".join(dict.fromkeys(filter(None, title_parts)))
        rendered = self.template.substitute(
            language=text(self.language), title=text(title), description=text(description or self.headline or self.name),
            home_link=home_link, top_link=text_link("#top", self.labels["top"], "↑", "top-link"),
            skip=text(self.labels["skip"]), navigation=navigation,
            main=main, footer_links=footer_links, custom_style=custom, script=script,
        )
        (self.destination / filename).write_text(rendered, encoding="utf-8")

    def contacts(self):
        return '<div class="contact-links">' + "".join(self.contact_links) + "</div>" if self.contact_links else ""

    def hero(self):
        portrait = self.figure(self.data.get("portrait"), "hero-image", eager=True)
        role = f'<p class="role">{text(self.headline)}</p>' if self.headline and self.headline != self.name else ""
        identity = f'<div><h1 id="name">{text(self.name)}</h1>{role}</div>'
        intro = paragraphs(self.data.get("intro"))
        action_key = next(iter(self.nav_items), "")
        action = ""
        if action_key:
            label = self.labels["view_projects"] if action_key == "projects" else self.nav_items[action_key]
            action = text_link(f"#{action_key}", label, "↓")
        facts = "".join(
            f'<li><strong>{text(item["value"])}</strong> {text(item["label"])}</li>'
            for item in self.data.get("metrics", [])
        )
        facts_block = f'<ul class="supporting-facts">{facts}</ul>' if facts else ""
        intro_content = intro + facts_block + action
        intro_block = f'<div class="hero-intro">{intro_content}</div>' if intro_content else ""
        hero_class = "hero has-image" if portrait else "hero"
        content = f"<div>{identity}{intro_block}</div>{portrait}" if portrait else identity + intro_block
        return f'<section class="{hero_class}" aria-labelledby="name">{content}</section>'

    def home(self):
        blocks = {
            "projects": "\n".join(self.project(index, project) for index, project in enumerate(self.projects)),
            "strengths": fact_list(self.data.get("strengths")),
            "experience": timeline(self.data.get("experience", [])),
            "skills": fact_list(self.data.get("skill_groups")) + tags(self.data.get("skills")),
            "education": timeline(self.data.get("education", [])),
            "contact": self.contacts(),
        }
        sections = "\n".join(section(key, self.labels[key], blocks[key]) for key in self.section_order)
        return f'<main id="main" class="shell" tabindex="-1">\n{self.hero()}\n{sections}\n</main>'

    def flow(self, project, reveal=False):
        steps = project.get("process")
        if not steps:
            return ""
        items = []
        for step in steps:
            detail = f'<span>{text(step["summary"])}</span>' if step.get("summary") else ""
            items.append(f'<li><strong>{text(step["title"])}</strong>{detail}</li>')
        caption = project.get("process_title") or self.labels["flow"]
        attributes = ' data-reveal' if reveal else ""
        return (
            f'<figure class="feature-flow"{attributes}><figcaption>{text(caption)}</figcaption>'
            f'<ol class="flow-steps">{"".join(items)}</ol></figure>'
        )

    def project(self, index, project):
        featured = index == 0
        page = self.project_pages.get(index)
        url = page or (public_url(project["url"]) if project.get("url") else "")
        title = link(url, project["title"]) if url else text(project["title"])
        heading = f'<h3>{title}</h3>'
        meta = metadata(project.get("role"), project.get("period"))
        meta_block = f'<p class="metadata">{meta}</p>' if meta else ""
        summary = paragraphs(project.get("summary"))
        if project.get("status"):
            status_label = text(self.labels["status"])
            summary += f'<p class="project-status"><strong>{status_label}</strong> {text(project["status"])}</p>'
        if not page:
            summary += tags(project.get("tags"))
        action = ""
        if url:
            label = self.labels["featured_detail"] if featured else self.labels["row_detail"]
            action = text_link(url, label, "→", "" if featured else "row-link", f'{label} {project["title"]}')

        if featured:
            visual = self.flow(project, reveal=True) or self.figure(project.get("cover"), "featured-cover", eager=True)
            featured_summary = f'<div class="featured-summary">{summary}</div>' if summary else ""
            return (
                f'<article class="featured-project"><div class="featured-copy">{meta_block}'
                f'{heading}{featured_summary}{action}</div>{visual}</article>'
            )
        cover = self.figure(project.get("cover"), "project-cover")
        description = f'<div class="project-summary">{summary}</div>' if summary else ""
        return f'<article class="project-row"><div>{cover}{heading}{meta_block}</div>{description}{action}</article>'

    def detail(self, project, featured=False):
        back = text_link("index.html#projects", self.labels["back"], "←", "back-link")
        meta = metadata(project.get("role"), project.get("period"))
        meta_block = f'<p class="metadata meta">{meta}</p>' if meta else ""
        summary = paragraphs(project.get("summary"))
        summary_block = f'<div class="prose">{summary}</div>' if summary else ""
        project_link = (
            '<div class="detail-action">' + text_link(public_url(project["url"]), self.labels["detail"], "↗") + "</div>"
            if project.get("url") else ""
        )
        details = []
        for block in project.get("sections", []):
            heading = f'<h2>{text(block["title"])}</h2>' if block.get("title") else ""
            body = paragraphs(block.get("body"))
            prose = f'<div class="prose">{body}</div>' if body else ""
            details.append(f'<div class="detail-block">{heading}{prose}{self.figure(block.get("image"), "detail-image")}</div>')
        gallery = "\n".join(self.figure(item, "detail-image") for item in project.get("gallery", []))
        cover = self.figure(project.get("cover"), "detail-image", eager=True)
        if project.get("status"):
            status_label = text(self.labels["status"])
            details.append(
                f'<div class="detail-block"><h2>{status_label}</h2>'
                f'<div class="prose">{paragraphs(project["status"])}</div></div>'
            )
        flow = self.flow(project) if not featured or not project.get("sections") else ""
        if flow:
            flow = f'<div class="detail-block">{flow}</div>'
        body = "\n".join(details)
        return (
            f'<main id="main" class="shell detail" tabindex="-1">{back}<article><header><h1>{text(project["title"])}</h1>'
            f'{meta_block}{tags(project.get("tags"))}{summary_block}{project_link}</header>'
            f'{cover}\n{flow}\n{body}\n{gallery}</article></main>'
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--styles", type=Path, help="Optional CSS overrides")
    args = parser.parse_args()
    destination = args.destination.absolute()
    try:
        if destination.exists() or destination.is_symlink():
            raise ValueError("Destination already exists. Use a new directory.")
        source = args.data.resolve(strict=True)
        data = json.loads(source.read_text(encoding="utf-8-sig"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".skill-website-", dir=destination.parent) as staging:
            site_dir = Path(staging) / "site"
            site_dir.mkdir()
            Site(data, source.parent, site_dir, args.styles).build()
            if destination.exists() or destination.is_symlink():
                raise ValueError("Destination already exists. Use a new directory.")
            site_dir.rename(destination)
    except (OSError, KeyError, ValueError, TypeError, AttributeError) as error:
        parser.exit(1, f"Cannot build site: {error}\n")
    print(destination / "index.html")


if __name__ == "__main__":
    main()
