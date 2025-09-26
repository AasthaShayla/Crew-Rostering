#!/usr/bin/env python3
"""
Startup script for the Crew Rostering API server
"""

import os
import sys
from api.app import app, socketio

if __name__ == '__main__':
    # Set environment variables for development
    os.environ.setdefault('DEBUG', 'True')
    # Default backend port aligned with frontend .env (5050)
    os.environ.setdefault('PORT', '5050')
    
    port = int(os.environ.get('PORT', 5050))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print("=" * 60)
    print("🚀 Crew Rostering Optimization System - Backend Server")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print(f"Data Path: {os.path.join(os.path.dirname(__file__), 'data')}")
    print("\n📡 Available API Endpoints:")
    print("  GET  /api/health              - Health check")
    print("  GET  /api/data/flights        - Get flights data")
    print("  GET  /api/data/crew           - Get crew data")
    print("  POST /api/optimize            - Run optimization")
    print("  POST /api/reoptimize          - Run what-if scenario")
    print("  GET  /api/roster/current      - Get current roster")
    print("  GET  /api/roster/baseline     - Get baseline roster")
    print("\n🌐 WebSocket Events:")
    print("  optimization_progress         - Real-time optimization updates")
    print("  reoptimization_complete       - What-if scenario results")
    print("\n✨ Frontend: http://localhost:3000")
    print("=" * 60)
    
    try:
        # Allow Werkzeug in dev for Flask-SocketIO
        socketio.run(app, host='0.0.0.0', port=port, debug=debug, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        sys.exit(1)