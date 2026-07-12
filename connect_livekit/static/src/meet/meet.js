/* Standalone LiveKit meeting page (no Odoo web client dependency).
 *
 * Reads the guest token from the #lk-meet dataset, asks for a display
 * name, POSTs /livekit/meet/<token>/join for a room JWT and renders a
 * simple participant grid with mic/camera/leave controls.
 */
(function () {
    "use strict";

    let room = null;

    function el(tag, className, parent) {
        const node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (parent) {
            parent.appendChild(node);
        }
        return node;
    }

    function tileId(identity) {
        return "lk-tile-" + identity.replace(/[^a-zA-Z0-9_-]/g, "_");
    }

    function ensureTile(grid, participant) {
        let tile = document.getElementById(tileId(participant.identity));
        if (!tile) {
            tile = el("div", "lk-tile", grid);
            tile.id = tileId(participant.identity);
            const label = el("div", "lk-tile-name", tile);
            label.textContent = participant.name || participant.identity;
        }
        return tile;
    }

    function removeTile(participant) {
        const tile = document.getElementById(tileId(participant.identity));
        if (tile) {
            tile.remove();
        }
    }

    function attachTrack(grid, track, participant) {
        const tile = ensureTile(grid, participant);
        const media = track.attach();
        media.classList.add("lk-media-" + track.kind);
        tile.appendChild(media);
    }

    function detachTrack(track) {
        track.detach().forEach(function (media) {
            media.remove();
        });
    }

    function buildControls(root, grid) {
        const bar = el("div", "lk-controls", root);
        const micBtn = el("button", "lk-btn", bar);
        micBtn.textContent = "Mute";
        micBtn.onclick = async function () {
            const enabled = room.localParticipant.isMicrophoneEnabled;
            await room.localParticipant.setMicrophoneEnabled(!enabled);
            micBtn.textContent = enabled ? "Unmute" : "Mute";
        };
        const camBtn = el("button", "lk-btn", bar);
        camBtn.textContent = "Camera Off";
        camBtn.onclick = async function () {
            const enabled = room.localParticipant.isCameraEnabled;
            await room.localParticipant.setCameraEnabled(!enabled);
            camBtn.textContent = enabled ? "Camera On" : "Camera Off";
        };
        const leaveBtn = el("button", "lk-btn lk-btn-leave", bar);
        leaveBtn.textContent = "Leave";
        leaveBtn.onclick = async function () {
            await room.disconnect();
            root.innerHTML = "";
            const bye = el("div", "lk-status", root);
            bye.textContent = "You left the meeting.";
        };
        return bar;
    }

    async function join(root, guestToken, displayName) {
        root.innerHTML = "";
        const status = el("div", "lk-status", root);
        status.textContent = "Connecting…";

        const resp = await fetch(
            "/livekit/meet/" + encodeURIComponent(guestToken) + "/join",
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ display_name: displayName }),
            }
        );
        if (!resp.ok) {
            status.textContent = "Could not join the meeting (" + resp.status + ").";
            return;
        }
        const data = await resp.json();

        const grid = el("div", "lk-grid", root);
        room = new LivekitClient.Room({ adaptiveStream: true, dynacast: true });
        room
            .on(LivekitClient.RoomEvent.TrackSubscribed, function (track, pub, participant) {
                attachTrack(grid, track, participant);
            })
            .on(LivekitClient.RoomEvent.TrackUnsubscribed, function (track) {
                detachTrack(track);
            })
            .on(LivekitClient.RoomEvent.ParticipantConnected, function (participant) {
                ensureTile(grid, participant);
            })
            .on(LivekitClient.RoomEvent.ParticipantDisconnected, function (participant) {
                removeTile(participant);
            })
            .on(LivekitClient.RoomEvent.LocalTrackPublished, function (pub, participant) {
                if (pub.track && pub.track.kind === "video") {
                    attachTrack(grid, pub.track, participant);
                }
            })
            .on(LivekitClient.RoomEvent.Disconnected, function () {
                status.textContent = "Disconnected.";
            });

        await room.connect(data.ws_url, data.token);
        status.remove();
        buildControls(root, grid);
        ensureTile(grid, room.localParticipant);
        try {
            await room.localParticipant.enableCameraAndMicrophone();
        } catch (err) {
            // Camera may be missing/blocked: fall back to audio only.
            try {
                await room.localParticipant.setMicrophoneEnabled(true);
            } catch (err2) {
                console.error("LiveKit: no media devices available", err2);
            }
        }
    }

    function buildJoinForm(root, guestToken, roomTitle) {
        const box = el("div", "lk-join", root);
        const title = el("h2", "lk-title", box);
        title.textContent = roomTitle || "Meeting";
        const input = el("input", "lk-name", box);
        input.type = "text";
        input.placeholder = "Your name";
        input.maxLength = 64;
        const btn = el("button", "lk-btn lk-btn-join", box);
        btn.textContent = "Join Meeting";
        const go = function () {
            join(root, guestToken, input.value.trim()).catch(function (err) {
                console.error("LiveKit join failed", err);
                const status = el("div", "lk-status", root);
                status.textContent = "Connection failed: " + err.message;
            });
        };
        btn.onclick = go;
        input.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter") {
                go();
            }
        });
        input.focus();
    }

    document.addEventListener("DOMContentLoaded", function () {
        const root = document.getElementById("lk-meet");
        if (!root) {
            return;
        }
        buildJoinForm(root, root.dataset.guestToken, root.dataset.roomTitle);
    });
})();
