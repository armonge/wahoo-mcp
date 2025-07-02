#!/usr/bin/env python3
"""Test script to validate Wahoo API credentials"""

import os
import sys
import httpx
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_wahoo_credentials():
    """Test if Wahoo credentials are valid by making a simple API call"""

    # Get access token from environment
    access_token = os.getenv("WAHOO_ACCESS_TOKEN")

    if not access_token:
        print("❌ Error: WAHOO_ACCESS_TOKEN not found in environment")
        print("Run 'make auth' to obtain an access token")
        return False

    # Test API endpoint - list workouts with limit 1
    url = "https://api.wahooligan.com/v1/workouts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    params = {"page": 1, "per_page": 1}

    print("🔍 Testing Wahoo API credentials...")
    print(f"   Token: {access_token[:10]}...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                print("✅ Success! Credentials are valid")
                print(f"   Found {len(data.get('workouts', []))} workout(s)")
                print("\n📋 Response body:")
                print(f"{response.text}")
                return True
            elif response.status_code == 401:
                print("❌ Invalid credentials: Authentication failed")
                print("   The access token may be expired or invalid")
                return False
            else:
                print(f"❌ API request failed with status: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Error testing credentials: {str(e)}")
            return False


if __name__ == "__main__":
    success = asyncio.run(test_wahoo_credentials())
    sys.exit(0 if success else 1)
