/** @odoo-module **/

/**
 * Verto WebRTC Client for FreeSWITCH
 * Implements JSON-RPC over WebSocket for Verto signaling
 * Features: reconnection, session recovery (verto.attach), heartbeat
 */
export class VertoClient {
    constructor(options) {
        this.socketUrl = options.socketUrl;
        this.login = options.login;
        this.domain = (options.domain || '').trim();
        this.password = options.password;
        this.callerName = options.callerName || options.login;
        this.callerNumber = options.callerNumber || options.login;
        
        this.ws = null;
        this.sessionId = this._loadOrCreateSessionId();
        this.rpcId = 1;
        this.pendingRequests = new Map();
        this.currentCall = null;
        this.localStream = null;
        this.peerConnection = null;
        this.remoteAudio = null;
        
        this.onStateChange = options.onStateChange || (() => {});
        this.onCallStateChange = options.onCallStateChange || (() => {});
        this.onError = options.onError || (() => {});
        
        this.state = 'disconnected';
        this.callState = 'idle';
        
        // Reconnection settings
        this.intentionalDisconnect = false;
        this.reconnectAttempt = 0;
        this.reconnectTimer = null;
        this.maxReconnectAttempts = 10;
        this.baseReconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        
        // Heartbeat settings
        this.heartbeatTimer = null;
        this.heartbeatInterval = 25000;
        this.lastPong = Date.now();
        
        // ICE settings
        this.iceGatheringTimeout = 10000;
        
        this.iceServers = options.iceServers || [
            { urls: 'stun:stun.l.google.com:19302' }
        ];
    }
    
    _loadOrCreateSessionId() {
        const storageKey = 'verto_session_id';
        let sessionId = null;
        try {
            sessionId = localStorage.getItem(storageKey);
        } catch (e) {}
        
        if (!sessionId) {
            sessionId = this._generateUUID();
            try {
                localStorage.setItem(storageKey, sessionId);
            } catch (e) {}
        }
        return sessionId;
    }

    _generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    _setState(state) {
        this.state = state;
        this.onStateChange(state);
    }

    _setCallState(state, data) {
        this.callState = state;
        this.onCallStateChange(state, data || {});
    }

    _appendDomain(value) {
        if (!value || !this.domain || value.includes('@')) {
            return value;
        }
        return `${value}@${this.domain}`;
    }

    async connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }

        this.intentionalDisconnect = false;
        this._setState('connecting');
        
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.socketUrl);
                
                this.ws.onopen = async () => {
                    console.log('[Verto] WebSocket connected');
                    this.reconnectAttempt = 0;
                    this._clearReconnectTimer();
                    
                    try {
                        await this._login();
                        this._startHeartbeat();
                        
                        // Try to recover active call if exists
                        if (this.currentCall && this.currentCall.callId) {
                            await this._attemptCallRecovery();
                        }
                        resolve();
                    } catch (error) {
                        reject(error);
                    }
                };
                
                this.ws.onmessage = (event) => {
                    try {
                        this._handleMessage(JSON.parse(event.data));
                    } catch (error) {
                        console.error('[Verto] Message parse error:', error);
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('[Verto] WebSocket error:', error);
                };
                
                this.ws.onclose = (event) => {
                    console.log('[Verto] WebSocket closed:', event.code, event.reason);
                    this._stopHeartbeat();
                    this._rejectPendingRequests('Connection closed');
                    
                    if (this.intentionalDisconnect) {
                        this._setState('disconnected');
                        this._cleanupCall();
                    } else {
                        this._setState('disconnected');
                        this._scheduleReconnect();
                    }
                };
            } catch (error) {
                this._setState('error');
                reject(error);
            }
        });
    }

    disconnect() {
        this.intentionalDisconnect = true;
        this._clearReconnectTimer();
        this._stopHeartbeat();
        
        if (this.currentCall) {
            this.hangup();
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this._cleanupCall();
        this._setState('disconnected');
    }
    
    _scheduleReconnect() {
        if (this.intentionalDisconnect) return;
        if (this.reconnectAttempt >= this.maxReconnectAttempts) {
            console.log('[Verto] Max reconnect attempts reached');
            this._setState('error');
            this.onError('Connection lost. Max reconnect attempts reached.');
            return;
        }
        
        const delay = Math.min(
            this.baseReconnectDelay * Math.pow(2, this.reconnectAttempt) + Math.random() * 1000,
            this.maxReconnectDelay
        );
        
        console.log(`[Verto] Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempt + 1})`);
        this._setState('reconnecting');
        
        this.reconnectTimer = setTimeout(async () => {
            this.reconnectAttempt++;
            try {
                await this.connect();
            } catch (error) {
                console.error('[Verto] Reconnect failed:', error);
            }
        }, delay);
    }
    
    _clearReconnectTimer() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
    
    _startHeartbeat() {
        this._stopHeartbeat();
        this.lastPong = Date.now();
        
        this.heartbeatTimer = setInterval(() => {
            if (Date.now() - this.lastPong > this.heartbeatInterval * 2) {
                console.log('[Verto] Heartbeat timeout, reconnecting...');
                this.ws?.close();
                return;
            }
            
            this._sendRpc('echo', {}).then(() => {
                this.lastPong = Date.now();
            }).catch(() => {
                // Even an error response means the connection is alive
                this.lastPong = Date.now();
            });
        }, this.heartbeatInterval);
    }
    
    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }
    
    _rejectPendingRequests(reason) {
        for (const [id, { reject }] of this.pendingRequests) {
            reject(new Error(reason));
        }
        this.pendingRequests.clear();
    }
    
    async _attemptCallRecovery() {
        if (!this.currentCall || !this.currentCall.callId) return;
        
        console.log('[Verto] Attempting call recovery for:', this.currentCall.callId);
        
        try {
            await this._sendRpc('verto.attach', {
                sessid: this.sessionId,
                dialogParams: {
                    callID: this.currentCall.callId
                }
            });
        } catch (error) {
            console.log('[Verto] Call recovery failed, call may have ended:', error);
            this._cleanupCall();
        }
    }

    _cleanupCall() {
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
            this.localStream = null;
        }
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        if (this.remoteAudio) {
            this.remoteAudio.pause();
            this.remoteAudio.srcObject = null;
        }
        this.currentCall = null;
        this._setCallState('idle');
    }

    _sendRpc(method, params = {}) {
        const id = this.rpcId++;
        const message = {
            jsonrpc: '2.0',
            id: id,
            method: method,
            params: params
        };
        
        console.log('[Verto] Sending:', method, params);
        this.ws.send(JSON.stringify(message));
        
        return new Promise((resolve, reject) => {
            this.pendingRequests.set(id, { resolve, reject });
            setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    reject(new Error('Request timeout'));
                }
            }, 30000);
        });
    }

    async _login() {
        try {
            const result = await this._sendRpc('login', {
                login: this._appendDomain(this.login),
                passwd: this.password,
                sessid: this.sessionId
            });
            
            console.log('[Verto] Login successful');
            this._setState('registered');
            return result;
        } catch (error) {
            console.error('[Verto] Login failed:', error);
            this._setState('error');
            this.onError('Login failed');
            throw error;
        }
    }

    _handleMessage(msg) {
        console.log('[Verto] Received:', msg);
        
        if (msg.id && this.pendingRequests.has(msg.id)) {
            const { resolve, reject } = this.pendingRequests.get(msg.id);
            this.pendingRequests.delete(msg.id);
            
            if (msg.error) {
                reject(msg.error);
            } else {
                resolve(msg.result);
            }
            return;
        }
        
        if (msg.method) {
            this._handleEvent(msg);
        }
    }

    _handleEvent(msg) {
        const method = msg.method;
        const params = msg.params || {};
        
        switch (method) {
            case 'verto.answer':
                this._handleAnswer(params);
                break;
            case 'verto.media':
                this._handleMedia(params);
                break;
            case 'verto.bye':
                this._handleBye(params);
                break;
            case 'verto.display':
                this._handleDisplay(params);
                break;
            case 'verto.invite':
                this._handleInvite(params);
                break;
            case 'verto.attach':
                this._handleAttach(params);
                break;
            case 'verto.punt':
                this._handlePunt(params);
                break;
            case 'verto.event':
                this._handleVertoEvent(params);
                break;
            default:
                console.log('[Verto] Unhandled event:', method);
        }
        
        if (msg.id) {
            this.ws.send(JSON.stringify({
                jsonrpc: '2.0',
                id: msg.id,
                result: { method: method }
            }));
        }
    }
    
    _handleDisplay(params) {
        const dp = params.dialogParams || {};
        const name = params.display_name || dp.display_name || '';
        const number = params.display_number || dp.display_number || '';

        if (this.currentCall) {
            if (name) this.currentCall.callerName = name;
            if (number) this.currentCall.callerNumber = number;
            this._setCallState(this.callState, {
                callerName: this.currentCall.callerName,
                callerNumber: this.currentCall.callerNumber
            });
        }
    }
    
    async _handleAttach(params) {
        console.log('[Verto] Received attach (call recovery):', params);

        const callId = params.callID || (params.dialogParams || {}).callID;

        // Only recover our active call, ignore stale sessions
        if (!this.currentCall || this.currentCall.callId !== callId) {
            console.log('[Verto] Ignoring attach for unknown call:', callId);
            return;
        }

        if (!params.sdp) return;

        try {
            await this._setupMediaForRecovery(params.sdp);
            this._setCallState('active');
        } catch (error) {
            console.error('[Verto] Attach handling failed:', error);
        }
    }
    
    async _setupMediaForRecovery(remoteSdp) {
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
        }
        if (this.peerConnection) {
            this.peerConnection.close();
        }
        
        this.localStream = await this._getMediaStream();
        this.peerConnection = this._createPeerConnection();
        
        this.localStream.getTracks().forEach(track => {
            this.peerConnection.addTrack(track, this.localStream);
        });
        
        await this.peerConnection.setRemoteDescription({
            type: 'offer',
            sdp: remoteSdp
        });
        
        const answer = await this.peerConnection.createAnswer();
        await this.peerConnection.setLocalDescription(answer);
        
        await this._waitForIceGathering();
        
        await this._sendRpc('verto.answer', {
            sessid: this.sessionId,
            sdp: this.peerConnection.localDescription.sdp,
            dialogParams: {
                callID: this.currentCall.callId
            }
        });
    }
    
    _handlePunt(params) {
        console.log('[Verto] Server punt received:', params);
        this.intentionalDisconnect = true;
        this._cleanupCall();
        this._setState('error');
        this.onError('Session terminated by server');
        this.ws?.close();
    }
    
    _handleVertoEvent(params) {
        if (params.eventData?.dialogState) {
            this._handleDialogState(params.eventData.dialogState);
        }
    }
    
    _handleDialogState(state) {
        console.log('[Verto] Dialog state:', state);
        switch (state) {
            case 'trying':
            case 'early':
                this._setCallState('ringing');
                break;
            case 'active':
                this._setCallState('active');
                break;
            case 'hangup':
            case 'destroy':
                this._cleanupCall();
                break;
        }
    }

    async _handleAnswer(params) {
        console.log('[Verto] Call answered');
        
        if (params.sdp && this.peerConnection) {
            try {
                await this.peerConnection.setRemoteDescription({
                    type: 'answer',
                    sdp: params.sdp
                });
                this._setCallState('active');
            } catch (error) {
                console.error('[Verto] Error setting remote description:', error);
            }
        }
    }

    async _handleMedia(params) {
        if (params.sdp && this.peerConnection) {
            try {
                await this.peerConnection.setRemoteDescription({
                    type: 'answer',
                    sdp: params.sdp
                });
            } catch (error) {
                console.error('[Verto] Error setting media description:', error);
            }
        }
    }

    _handleBye(params) {
        console.log('[Verto] Call ended');
        this._cleanupCall();
    }

    async _handleInvite(params) {
        console.log('[Verto] Incoming call:', params);
        const dp = params.dialogParams || {};

        const callerName = params.caller_id_name || dp.caller_id_name || '';
        const callerNumber = params.caller_id_number || dp.caller_id_number || '';

        this.currentCall = {
            callId: params.callID || dp.callID,
            callerName,
            callerNumber,
            sdp: params.sdp,
            incoming: true
        };

        this._setCallState('incoming', { callerName, callerNumber });
    }

    async _getMediaStream() {
        if (!navigator.mediaDevices?.getUserMedia) {
            throw new Error('WebRTC not supported in this browser');
        }
        
        try {
            return await navigator.mediaDevices.getUserMedia({
                audio: true,
                video: false
            });
        } catch (error) {
            let message = 'Microphone access failed';
            if (error.name === 'NotAllowedError') {
                message = 'Microphone permission denied';
            } else if (error.name === 'NotFoundError') {
                message = 'No microphone found';
            } else if (error.name === 'NotReadableError') {
                message = 'Microphone in use by another application';
            }
            throw new Error(message);
        }
    }
    
    _createPeerConnection() {
        const pc = new RTCPeerConnection({
            iceServers: this.iceServers
        });
        
        pc.ontrack = (event) => {
            if (!this.remoteAudio) {
                this.remoteAudio = new Audio();
            }
            this.remoteAudio.srcObject = event.streams[0];
            this.remoteAudio.play().catch(err => {
                console.warn('[Verto] Audio autoplay blocked:', err);
                this.onError('Audio autoplay blocked. Click to enable audio.');
            });
        };
        
        pc.oniceconnectionstatechange = () => {
            console.log('[Verto] ICE connection state:', pc.iceConnectionState);
            if (pc.iceConnectionState === 'failed') {
                this.onError('Connection quality issues detected');
            }
        };
        
        return pc;
    }
    
    async _waitForIceGathering() {
        return new Promise((resolve) => {
            if (this.peerConnection.iceGatheringState === 'complete') {
                resolve();
                return;
            }
            
            const checkComplete = () => {
                if (this.peerConnection?.iceGatheringState === 'complete') {
                    this.peerConnection.onicegatheringstatechange = null;
                    resolve();
                }
            };
            
            this.peerConnection.onicegatheringstatechange = checkComplete;
            setTimeout(() => {
                if (this.peerConnection) {
                    this.peerConnection.onicegatheringstatechange = null;
                }
                resolve();
            }, this.iceGatheringTimeout);
        });
    }

    async call(destination) {
        if (this.state !== 'registered') {
            throw new Error('Not registered');
        }
        
        if (this.callState !== 'idle') {
            throw new Error('Call already in progress');
        }
        
        this._setCallState('calling');
        
        try {
            this.localStream = await this._getMediaStream();
            this.peerConnection = this._createPeerConnection();
            
            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });
            
            const offer = await this.peerConnection.createOffer({
                offerToReceiveAudio: true,
                offerToReceiveVideo: false
            });
            await this.peerConnection.setLocalDescription(offer);
            
            await this._waitForIceGathering();
            
            const callId = this._generateUUID();
            this.currentCall = { callId, destination };

            await this._sendRpc('verto.invite', {
                sessid: this.sessionId,
                sdp: this.peerConnection.localDescription.sdp,
                dialogParams: {
                    callID: callId,
                    destination_number: destination,
                    caller_id_name: this.callerName,
                    caller_id_number: this.callerNumber,
                    remote_caller_id_name: destination,
                    remote_caller_id_number: destination,
                    useVideo: false,
                    useStereo: false
                }
            });
            
            this._setCallState('ringing');
            
        } catch (error) {
            console.error('[Verto] Call failed:', error);
            this._cleanupCall();
            this.onError('Call failed: ' + error.message);
            throw error;
        }
    }

    async answer() {
        if (!this.currentCall || !this.currentCall.incoming) {
            throw new Error('No incoming call');
        }
        
        try {
            this.localStream = await this._getMediaStream();
            this.peerConnection = this._createPeerConnection();
            
            this.localStream.getTracks().forEach(track => {
                this.peerConnection.addTrack(track, this.localStream);
            });
            
            await this.peerConnection.setRemoteDescription({
                type: 'offer',
                sdp: this.currentCall.sdp
            });
            
            const answer = await this.peerConnection.createAnswer();
            await this.peerConnection.setLocalDescription(answer);
            
            await this._waitForIceGathering();
            
            await this._sendRpc('verto.answer', {
                sessid: this.sessionId,
                sdp: this.peerConnection.localDescription.sdp,
                dialogParams: {
                    callID: this.currentCall.callId,
                    caller_id_name: this.callerName,
                    caller_id_number: this.callerNumber
                }
            });
            
            this._setCallState('active');
            
        } catch (error) {
            console.error('[Verto] Answer failed:', error);
            this._cleanupCall();
            this.onError('Answer failed: ' + error.message);
            throw error;
        }
    }

    async hangup() {
        if (!this.currentCall) {
            return;
        }
        
        try {
            await this._sendRpc('verto.bye', {
                sessid: this.sessionId,
                dialogParams: {
                    callID: this.currentCall.callId
                }
            });
        } catch (error) {
            console.error('[Verto] Hangup error:', error);
        }
        
        this._cleanupCall();
    }

    sendDTMF(digit) {
        if (!this.currentCall || this.callState !== 'active') {
            return;
        }
        
        this._sendRpc('verto.info', {
            sessid: this.sessionId,
            dtmf: digit,
            dialogParams: {
                callID: this.currentCall.callId
            }
        });
    }

    toggleMute() {
        if (this.localStream) {
            const audioTrack = this.localStream.getAudioTracks()[0];
            if (audioTrack) {
                audioTrack.enabled = !audioTrack.enabled;
                return !audioTrack.enabled;
            }
        }
        return false;
    }
}
