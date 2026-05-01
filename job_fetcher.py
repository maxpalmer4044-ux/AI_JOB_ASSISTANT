from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import urlparse

import requests


def _strip_html(raw_html: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", raw_html)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|li|h[1-6]|section|article)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = _strip_html(str(value))
    return re.sub(r"\s+", " ", text).strip()


def _find_jobposting(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        for item in payload:
            found = _find_jobposting(item)
            if found:
                return found
    if isinstance(payload, dict):
        item_type = payload.get("@type")
        if item_type == "JobPosting" or (isinstance(item_type, list) and "JobPosting" in item_type):
            return payload
        graph = payload.get("@graph")
        if graph:
            return _find_jobposting(graph)
        for value in payload.values():
            found = _find_jobposting(value)
            if found:
                return found
    return None


def _json_ld_jobposting(page_html: str) -> dict[str, Any] | None:
    scripts = re.findall(
        r"(?is)<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        page_html,
    )
    for script in scripts:
        try:
            payload = json.loads(html.unescape(script).strip())
        except json.JSONDecodeError:
            continue
        found = _find_jobposting(payload)
        if found:
            return found
    return None


def _meta_content(page_html: str, name: str) -> str:
    patterns = [
        rf"(?is)<meta[^>]+name=[\"']{re.escape(name)}[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>",
        rf"(?is)<meta[^>]+property=[\"']{re.escape(name)}[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def _title(page_html: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", page_html)
    return _clean_text(match.group(1)) if match else ""


def _normalized_lines(text: str) -> list[str]:
    lines: list[str] = []
    seen_repeats: dict[str, int] = {}
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        key = line.lower()
        seen_repeats[key] = seen_repeats.get(key, 0) + 1
        if seen_repeats[key] > 2:
            continue
        lines.append(line)
    return lines


def _is_linkedin_host(host: str) -> bool:
    return host.lower().endswith("linkedin.com")


def _clean_linkedin_title(title: str) -> str:
    cleaned = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^.*?\bhiring\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+in\s+.+$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _extract_after_line(lines: list[str], needle: str, start_index: int = 0) -> tuple[str, int | None]:
    needle_lower = needle.lower()
    for index in range(start_index, len(lines)):
        if lines[index].lower() == needle_lower and index + 1 < len(lines):
            return lines[index + 1], index + 1
    return "", None


def _linkedin_core_fields(lines: list[str], page_title: str) -> tuple[str, str, str]:
    title = ""
    company = ""
    location = ""

    for index, line in enumerate(lines):
        if line.lower() == "apply" and index >= 3:
            title = lines[index - 3]
            company = lines[index - 2]
            location = lines[index - 1]
            break

    if not title:
        title, title_index = _extract_after_line(lines, "Join to apply for the")
        if title_index is not None:
            company, company_index = _extract_after_line(lines, "role at", title_index)
            if company_index is not None and company_index + 1 < len(lines):
                location = lines[company_index + 1]

    if not title:
        title = _clean_linkedin_title(page_title)
    return _clean_text(title), _clean_text(company), _clean_text(location)


def _extract_linkedin_description(lines: list[str], full_text: str) -> str:
    start_markers = [
        "What can you expect?",
        "About the job",
        "About the role",
        "The role",
        "Job description",
    ]
    end_markers = [
        "Show more",
        "Show less",
        "Seniority level",
        "Employment type",
        "Job function",
        "Industries",
        "Referrals increase your chances",
        "Similar jobs",
        "People also viewed",
        "Explore top content on LinkedIn",
    ]

    start = None
    for marker in start_markers:
        matches = [index for index, line in enumerate(lines) if line.lower() == marker.lower()]
        if matches:
            later_matches = [index for index in matches if index > 20]
            start = later_matches[0] if later_matches else matches[-1]
            break

    if start is None:
        return full_text[:24000]

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if any(lines[index].lower() == marker.lower() for marker in end_markers):
            end = index
            break

    description_lines = lines[start:end]
    noise_fragments = [
        "sign in",
        "join now",
        "email or phone",
        "password",
        "forgot password",
        "linkedin user agreement",
        "cookie policy",
        "privacy policy",
        "use ai to assess",
        "tailor my resume",
        "am i a good fit",
        "save",
        "report this job",
        "apply",
        "see who",
        "get notified",
        "set alert",
    ]
    filtered = [
        line
        for line in description_lines
        if not any(fragment in line.lower() for fragment in noise_fragments)
    ]
    while filtered and filtered[0].lower() == "about the job":
        filtered.pop(0)
    return "\n".join(filtered).strip()


def _find_company_site(description: str, company: str, page_host: str) -> str:
    urls = re.findall(r"https?://[^\s),]+", description)
    for url in urls:
        host = urlparse(url).netloc.lower()
        if "linkedin.com" not in host:
            return url.rstrip(".")

    domain_matches = re.findall(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", description, flags=re.IGNORECASE)
    blocked_hosts = {"linkedin.com", "www.linkedin.com", page_host.lower()}
    for domain in domain_matches:
        clean_domain = domain.lower().strip(".")
        if clean_domain not in blocked_hosts and "linkedin" not in clean_domain:
            return f"https://{clean_domain}"

    if company:
        compact_company = re.sub(r"[^a-z0-9]", "", company.lower())
        for domain in domain_matches:
            compact_domain = re.sub(r"[^a-z0-9]", "", domain.lower())
            if compact_company and compact_company[:5] in compact_domain:
                return f"https://{domain.lower()}"
    return ""


def _extract_between_markers(lines: list[str], start_markers: list[str], end_markers: list[str]) -> str:
    start = None
    for marker in start_markers:
        matches = [index for index, line in enumerate(lines) if line.lower() == marker.lower()]
        if matches:
            start = matches[0]
            break
    if start is None:
        return ""

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if any(lines[index].lower() == marker.lower() for marker in end_markers):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _clean_generic_job_text(page_text: str, host: str) -> str:
    lines = _normalized_lines(page_text)
    host_lower = host.lower()
    common_end_markers = [
        "Apply for this job",
        "Apply now",
        "Submit application",
        "Similar jobs",
        "Powered by",
        "Privacy policy",
        "Cookie policy",
        "Equal opportunity",
    ]

    if "greenhouse.io" in host_lower or "greenhouse" in host_lower:
        extracted = _extract_between_markers(
            lines,
            ["About the role", "About the job", "Job description", "The role"],
            common_end_markers + ["Voluntary self-identification", "Demographic questions"],
        )
        if extracted:
            return extracted

    if "ashbyhq.com" in host_lower or "ashby" in host_lower:
        extracted = _extract_between_markers(
            lines,
            ["About this role", "About the role", "About the job", "What you'll do", "The role"],
            common_end_markers + ["Application", "Voluntary disclosures"],
        )
        if extracted:
            return extracted

    if "myworkdayjobs.com" in host_lower or "workday" in host_lower:
        extracted = _extract_between_markers(
            lines,
            ["Job Description", "About the role", "About this role", "The role"],
            common_end_markers + ["Job Posting End Date", "Similar Jobs"],
        )
        if extracted:
            return extracted

    start_signals = [
        "About the role",
        "About this role",
        "About the job",
        "Job description",
        "The role",
        "What you'll do",
        "Responsibilities",
    ]
    extracted = _extract_between_markers(lines, start_signals, common_end_markers)
    if extracted:
        return extracted

    noise_fragments = [
        "cookie",
        "privacy",
        "sign in",
        "create account",
        "subscribe",
        "job alert",
        "share this job",
        "view all jobs",
        "powered by",
    ]
    filtered = [
        line
        for line in lines
        if len(line) > 2 and not any(fragment in line.lower() for fragment in noise_fragments)
    ]
    return "\n".join(filtered).strip()


def _extract_json_text_values(value: Any, keys: set[str]) -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in keys and isinstance(nested, str):
                matches.append(_strip_html(nested))
            matches.extend(_extract_json_text_values(nested, keys))
    elif isinstance(value, list):
        for item in value:
            matches.extend(_extract_json_text_values(item, keys))
    return [match for match in matches if len(match) > 120]


def _embedded_json_description(page_html: str) -> str:
    scripts = re.findall(r"(?is)<script[^>]*>(.*?)</script>", page_html)
    for script in scripts:
        if not any(token in script.lower() for token in ["description", "jobdescription", "jobposting"]):
            continue
        for match in re.finditer(r"\{.*\}", script, flags=re.DOTALL):
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
            values = _extract_json_text_values(payload, {"description", "jobdescription", "content"})
            if values:
                return max(values, key=len)
    return ""


def fetch_job_posting(url: str) -> tuple[dict[str, str], str | None]:
    clean_url = (url or "").strip()
    parsed = urlparse(clean_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {}, "Enter a valid http or https job URL."

    try:
        response = requests.get(
            clean_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                )
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {}, f"Could not fetch that page: {exc}"

    page_html = response.text
    page_text = _strip_html(page_html)
    lowered = page_html.lower()
    if "linkedin.com/authwall" in lowered:
        return {}, "LinkedIn did not expose the job text publicly. Paste the JD text or use the official company JD link."

    job = _json_ld_jobposting(page_html) or {}
    hiring_org = job.get("hiringOrganization") if isinstance(job.get("hiringOrganization"), dict) else {}
    location = job.get("jobLocation")
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address") if isinstance(location, dict) else {}
    if not isinstance(address, dict):
        address = {}

    description = _strip_html(str(job.get("description") or ""))
    embedded_description = _embedded_json_description(page_html)
    if embedded_description and len(embedded_description) > len(description):
        description = embedded_description
    if len(description) < 250:
        description = _clean_generic_job_text(page_text, parsed.netloc) or page_text

    title = _clean_text(job.get("title")) or _title(page_html)
    company = _clean_text(hiring_org.get("name"))
    location_parts = [
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
    ]
    location_text = ", ".join(_clean_text(part) for part in location_parts if _clean_text(part))
    company_site = _clean_text(hiring_org.get("sameAs") or hiring_org.get("url"))
    if not company_site and not _is_linkedin_host(parsed.netloc):
        company_site = f"{parsed.scheme}://{parsed.netloc}"

    if _is_linkedin_host(parsed.netloc):
        lines = _normalized_lines(page_text)
        linkedin_title, linkedin_company, linkedin_location = _linkedin_core_fields(lines, title)
        linkedin_description = _extract_linkedin_description(lines, page_text)
        title = linkedin_title or _clean_linkedin_title(title)
        company = linkedin_company or company
        location_text = linkedin_location or location_text
        description = linkedin_description or description
        company_site = _find_company_site(description, company, parsed.netloc)

    if len(description) < 250 and not _is_linkedin_host(parsed.netloc):
        fallback = _meta_content(page_html, "description") or _meta_content(page_html, "og:description")
        description = _clean_text(fallback)

    if not _is_linkedin_host(parsed.netloc):
        cleaned_description = _clean_generic_job_text(description, parsed.netloc)
        if len(cleaned_description) > 250:
            description = cleaned_description

    if len(description) < 120:
        return {}, "The page loaded, but there was not enough job text to analyze. Paste the JD text instead."

    return {
        "job_title": title,
        "company": company,
        "location": location_text,
        "description": description[:24000],
        "jd_link": clean_url,
        "company_site": company_site,
    }, None
