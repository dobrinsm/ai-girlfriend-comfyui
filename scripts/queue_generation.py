#!/usr/bin/env python3
"""
Script to queue a generation through the AI Girlfriend API
"""

import argparse
import asyncio
import base64
import json
import sys
import time
from pathlib import Path

import httpx
import websockets


async def queue_avatar_generation(
    api_url: str,
    prompt: str,
    webcam_path: str = None,
    user_id: str = "test_user"
):
    """Queue an avatar generation"""
    async with httpx.AsyncClient() as client:
        files = {}
        data = {"prompt": prompt, "user_id": user_id}

        if webcam_path:
            files["webcam_image"] = open(webcam_path, "rb")

        response = await client.post(
            f"{api_url}/api/v1/generate/avatar",
            data=data,
            files=files,
            timeout=300.0
        )
        response.raise_for_status()
        return response.json()


async def queue_video_generation(
    api_url: str,
    image_path: str,
    prompt: str = "",
    user_id: str = "test_user"
):
    """Queue a video generation"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/api/v1/generate/video",
            params={
                "image_path": image_path,
                "prompt": prompt,
                "user_id": user_id
            },
            timeout=300.0
        )
        response.raise_for_status()
        return response.json()


async def queue_voice_generation(
    api_url: str,
    text: str,
    user_id: str = "test_user"
):
    """Queue a voice generation"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/api/v1/generate/voice",
            params={
                "text": text,
                "user_id": user_id
            },
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()


async def chat_websocket(
    ws_url: str,
    message: str,
    user_id: str = "test_user"
):
    """Connect to chat WebSocket"""
    uri = f"{ws_url}/ws/chat"

    async with websockets.connect(uri) as websocket:
        # Send message
        await websocket.send(json.dumps({
            "type": "chat",
            "message": message,
            "user_id": user_id
        }))

        # Receive updates
        print(f"User: {message}")
        print("AI: ", end="", flush=True)

        while True:
            try:
                response = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=60.0
                )
                data = json.loads(response)

                if data.get("type") == "chat_response":
                    print(data.get("text", ""))
                elif data.get("type") == "status":
                    print(f"\n[Status: {data.get('message')}]", end="", flush=True)
                elif data.get("type") == "complete":
                    print(f"\n[Complete in {data.get('total_time', 0):.2f}s]")
                    break
                elif data.get("type") == "error":
                    print(f"\n[Error: {data.get('message')}]")
                    break

            except asyncio.TimeoutError:
                print("\n[Timeout]")
                break


def main():
    parser = argparse.ArgumentParser(
        description="Queue AI Girlfriend generation"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Backend API URL"
    )
    parser.add_argument(
        "--ws-url",
        default="ws://localhost:8000",
        help="WebSocket URL"
    )
    parser.add_argument(
        "--type",
        choices=["avatar", "video", "voice", "chat"],
        required=True,
        help="Generation type"
    )
    parser.add_argument(
        "--prompt",
        help="Generation prompt"
    )
    parser.add_argument(
        "--image-path",
        help="Input image path (for video)"
    )
    parser.add_argument(
        "--webcam-path",
        help="Webcam image path (for avatar)"
    )
    parser.add_argument(
        "--text",
        help="Text for voice generation or chat"
    )
    parser.add_argument(
        "--user-id",
        default="test_user",
        help="User ID"
    )

    args = parser.parse_args()

    async def run():
        if args.type == "avatar":
            if not args.prompt:
                print("Error: --prompt required for avatar generation")
                sys.exit(1)

            result = await queue_avatar_generation(
                args.api_url,
                args.prompt,
                args.webcam_path,
                args.user_id
            )
            print(json.dumps(result, indent=2))

        elif args.type == "video":
            if not args.image_path:
                print("Error: --image-path required for video generation")
                sys.exit(1)

            result = await queue_video_generation(
                args.api_url,
                args.image_path,
                args.prompt or "",
                args.user_id
            )
            print(json.dumps(result, indent=2))

        elif args.type == "voice":
            if not args.text:
                print("Error: --text required for voice generation")
                sys.exit(1)

            result = await queue_voice_generation(
                args.api_url,
                args.text,
                args.user_id
            )
            print(json.dumps(result, indent=2))

        elif args.type == "chat":
            if not args.text:
                print("Error: --text required for chat")
                sys.exit(1)

            await chat_websocket(args.ws_url, args.text, args.user_id)

    asyncio.run(run())


if __name__ == "__main__":
    main()
