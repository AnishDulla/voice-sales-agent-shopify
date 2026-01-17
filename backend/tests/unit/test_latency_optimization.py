"""Test script to measure latency improvements in the optimized agent."""

import asyncio
import websockets
import json
import time
from datetime import datetime


async def test_latency():
    """Test the optimized agent's latency."""
    
    uri = "ws://localhost:8000/ws/voice/session"
    
    print("🚀 Starting latency test...")
    print("-" * 50)
    
    async with websockets.connect(uri) as websocket:
        # Start session
        await websocket.send(json.dumps({
            "type": "session.start",
            "data": {"session_id": f"test_{int(time.time())}"}
        }))
        
        # Wait for ready
        response = await websocket.recv()
        data = json.loads(response)
        assert data["type"] == "session.ready"
        print("✅ Session ready")
        
        # Test queries
        test_queries = [
            "Show me some hoodies",
            "What's the price of the cloud hoodie?",
            "Do you have any running shoes?"
        ]
        
        for query in test_queries:
            print(f"\n📝 Testing query: '{query}'")
            
            # Track timing
            start_time = time.time()
            first_chunk_time = None
            first_audio_time = None
            chunks_received = 0
            audio_chunks_received = 0
            
            # Send query
            await websocket.send(json.dumps({
                "type": "text.input",
                "data": {"text": query}
            }))
            
            print(f"⏱️  Sent at: 0.00s")
            
            # Collect responses
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                current_time = time.time() - start_time
                
                if data["type"] == "text.chunk":
                    chunks_received += 1
                    if first_chunk_time is None:
                        first_chunk_time = current_time
                        print(f"📝 First text chunk: {current_time:.2f}s - '{data['data']['text'][:50]}...'")
                    
                elif data["type"] == "audio.chunk":
                    audio_chunks_received += 1
                    if first_audio_time is None:
                        first_audio_time = current_time
                        print(f"🎵 First audio chunk: {current_time:.2f}s")
                    
                elif data["type"] == "agent.response":
                    total_time = time.time() - start_time
                    print(f"✅ Complete: {total_time:.2f}s")
                    print(f"   Text chunks: {chunks_received}")
                    print(f"   Audio chunks: {audio_chunks_received}")
                    
                    # Calculate improvement
                    if first_audio_time:
                        print(f"\n🎯 Time to first audio: {first_audio_time:.2f}s")
                        print(f"   (Target: 2-3s, Original: ~32s)")
                        
                        if first_audio_time < 5:
                            print(f"   ✨ EXCELLENT - {32/first_audio_time:.1f}x faster!")
                        elif first_audio_time < 10:
                            print(f"   ✅ GOOD - {32/first_audio_time:.1f}x faster!")
                        else:
                            print(f"   ⚠️  NEEDS IMPROVEMENT")
                    
                    break
                
                elif data["type"] == "error":
                    print(f"❌ Error: {data['data']['message']}")
                    break
            
            # Small delay between queries
            await asyncio.sleep(1)
    
    print("\n" + "=" * 50)
    print("🏁 Latency test complete!")


if __name__ == "__main__":
    asyncio.run(test_latency())