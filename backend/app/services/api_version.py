"""Utility to find the working Aula API version (handles 410 fallback)."""

API_BASE = "https://www.aula.dk/api/v"


def find_working_api_version(
    session,
    start_version: int = 22,
    access_token: str = "",
    max_attempts: int = 20,
) -> dict:
    """
    Try API versions starting from start_version, incrementing on HTTP 410.

    Returns dict with 'version' and 'profiles' on success.
    Raises RuntimeError if no working version is found.
    """
    version = start_version

    for _ in range(max_attempts):
        url = f"{API_BASE}{version}?method=profiles.getProfilesByLogin&access_token={access_token}"
        response = session.get(url, verify=True)

        if response.status_code == 410:
            version += 1
            continue
        elif response.status_code == 200:
            data = response.json().get("data", {})
            profiles = data.get("profiles", [])
            return {"version": version, "profiles": profiles}
        else:
            raise RuntimeError(
                f"Unexpected API response: {response.status_code}"
            )

    raise RuntimeError(
        f"Could not find working API version after {max_attempts} attempts (tried v{start_version}-v{version - 1})"
    )
