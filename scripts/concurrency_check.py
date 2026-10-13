from __future__ import annotations

import argparse
import asyncio

import httpx


async def create_tenant(client: httpx.AsyncClient, *, slug: str, name: str) -> str:
    response = await client.post("/tenants", json={"slug": slug, "name": name})
    response.raise_for_status()
    return str(response.json()["id"])


async def patch_tenant(
    client: httpx.AsyncClient,
    *,
    tenant_id: str,
    name: str,
    version: int,
) -> httpx.Response:
    return await client.patch(
        f"/tenants/{tenant_id}",
        json={"name": name, "version": version},
    )


async def run_patch_race(
    *,
    base_url: str,
    tenant_id: str | None,
    slug: str,
    name: str,
    version: int,
) -> list[httpx.Response]:
    """Send two PATCH requests with the same version and return both responses.

    Example:
        python scripts/concurrency_check.py --base-url http://localhost:8000 \
            --slug demo-race --name "Demo" --version 1
    """
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        if tenant_id is None:
            tenant_id = await create_tenant(client, slug=slug, name=name)

        tasks = [
            patch_tenant(client, tenant_id=tenant_id, name=name, version=version),
            patch_tenant(client, tenant_id=tenant_id, name=f"{name} v2", version=version),
        ]
        return await asyncio.gather(*tasks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Demonstrate optimistic locking by issuing concurrent PATCH requests "
            "with the same tenant version."
        )
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the API.")
    parser.add_argument(
        "--tenant-id", help="Tenant UUID to mutate. If omitted, a tenant is created first."
    )
    parser.add_argument("--slug", default="race-demo", help="Slug to use when creating a tenant.")
    parser.add_argument("--name", default="Race Demo", help="Name to use when creating a tenant.")
    parser.add_argument(
        "--version", type=int, default=1, help="Version shared by both concurrent PATCHes."
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    results = await run_patch_race(
        base_url=args.base_url,
        tenant_id=args.tenant_id,
        slug=args.slug,
        name=args.name,
        version=args.version,
    )

    successes = [result for result in results if result.status_code == 200]
    conflicts = [result for result in results if result.status_code == 409]
    print(f"successes={len(successes)} conflicts={len(conflicts)}")
    for result in results:
        print(f"status={result.status_code} body={result.text}")


if __name__ == "__main__":
    asyncio.run(main())
