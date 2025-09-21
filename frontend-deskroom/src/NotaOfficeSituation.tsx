import React, { useEffect, useState, useMemo } from "react";

/**
 * NotaOfficeSituation - Unified Dashboard for Meeting Rooms & Focus Rooms
 * ---------------------------------------------------------------------
 * 
 * Features:
 * - Integrated status board showing all spaces (meeting rooms + focus rooms)
 * - Interactive SVG map with real-time status
 * - Click-based reservation for meeting rooms
 * - Click-based claim/extend/release for focus rooms
 * - Real-time status updates
 */

// Types
interface Room {
  roomId: number;
  name: string;
  type: 'MEETING' | 'FOCUS' | 'LOUNGE';
  capacity: number;
  svgId?: string;
  status: 'AVAILABLE' | 'RESERVED' | 'OCCUPIED';
  current?: { until: string };
  next?: { start: string };
}

interface Reservation {
  id: number;
  start_time: string;
  end_time: string;
  status: string;
  created_at: string;
}

// Nota Office Layout (SVG Coordinates)
const OFFICE_LAYOUT = {
  // Meeting Rooms (10개 회의실)
  MEETING_ROOMS: [
    { id: 1, name: "Disagree&Commit", x: 50, y: 50, w: 200, h: 120 },
    { id: 2, name: "Ownership", x: 270, y: 50, w: 200, h: 120 },
    { id: 3, name: "Customer-Centric", x: 490, y: 50, w: 200, h: 120 },
    { id: 4, name: "Trust", x: 710, y: 50, w: 200, h: 120 },
    { id: 5, name: "Leadership Principle", x: 50, y: 190, w: 200, h: 120 },
    { id: 6, name: "회의실1", x: 270, y: 190, w: 180, h: 100 },
    { id: 7, name: "회의실2", x: 470, y: 190, w: 180, h: 100 },
    { id: 8, name: "회의실3", x: 670, y: 190, w: 180, h: 100 },
    { id: 9, name: "회의실4", x: 270, y: 310, w: 180, h: 100 },
    { id: 10, name: "회의실5", x: 470, y: 310, w: 180, h: 100 },
  ],
  // Focus Rooms (포커스룸)
  FOCUS_ROOMS: [
    { id: 11, name: "Focus-A", x: 50, y: 330, w: 80, h: 80 },
    { id: 12, name: "Focus-B", x: 140, y: 330, w: 80, h: 80 },
    { id: 13, name: "Focus-C", x: 670, y: 310, w: 80, h: 80 },
    { id: 14, name: "Focus-D", x: 760, y: 310, w: 80, h: 80 },
    { id: 15, name: "Focus-E", x: 860, y: 310, w: 80, h: 80 },
  ]
};

interface UserStatus {
  focus_room: {
    id: number;
    name: string;
    start_time: string;
    timer_duration: number;
  } | null;
  active_meeting_rooms: Array<{
    id: number;
    name: string;
    reservation_id: number;
    start_time: string;
    end_time: string;
  }>;
  upcoming_meeting_rooms: Array<{
    id: number;
    name: string;
    reservation_id: number;
    start_time: string;
    end_time: string;
  }>;
}

export default function NotaOfficeSituation() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [showPopover, setShowPopover] = useState(false);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [userStatus, setUserStatus] = useState<UserStatus | null>(null);

  // Fetch rooms status
  const fetchRoomsStatus = async () => {
    try {
      const response = await fetch('/api/rooms/status');
      const data = await response.json();
      setRooms(data);
      setLastUpdate(new Date().toLocaleTimeString());
    } catch (error) {
      console.error('Failed to fetch rooms status:', error);
    }
  };

  // Fetch user status
  const fetchUserStatus = async () => {
    try {
      const response = await fetch('/api/user/status');
      const data = await response.json();
      setUserStatus(data);
    } catch (error) {
      console.error('Failed to fetch user status:', error);
    }
  };

  // Fetch reservations for selected room
  const fetchReservations = async (roomId: number) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/rooms/${roomId}/reservations`);
      const data = await response.json();
      setReservations(data);
    } catch (error) {
      console.error('Failed to fetch reservations:', error);
      setReservations([]);
    } finally {
      setLoading(false);
    }
  };

  // Initial load and periodic refresh
  useEffect(() => {
    fetchRoomsStatus();
    fetchUserStatus();
    const interval = setInterval(() => {
      fetchRoomsStatus();
      fetchUserStatus();
    }, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  // Fetch reservations when room is selected
  useEffect(() => {
    if (selectedRoom && selectedRoom.type === 'MEETING') {
      fetchReservations(selectedRoom.roomId);
    }
  }, [selectedRoom]);

  // Handle room click
  const handleRoomClick = (roomId: number) => {
    const room = rooms.find(r => r.roomId === roomId);
    if (room) {
      setSelectedRoom(room);
      setShowPopover(true);
    }
  };

  // Refresh both rooms and user status
  const refreshAll = () => {
    fetchRoomsStatus();
    fetchUserStatus();
  };

  // Refresh user status only
  const refreshUserStatus = async () => {
    try {
      const response = await fetch('/api/user/status');
      if (response.ok) {
        const data = await response.json();
        setUserStatus(data);
      }
    } catch (error) {
      console.error('Failed to fetch user status:', error);
    }
  };

  // Close popover
  const closePopover = () => {
    setShowPopover(false);
    setSelectedRoom(null);
    setReservations([]);
  };

  // Get status colors
  const getStatusColors = (status: string) => {
    switch (status) {
      case 'AVAILABLE':
        return { bg: '#dcfce7', stroke: '#16a34a', text: '사용 가능' }; // green
      case 'RESERVED':
        return { bg: '#fef3c7', stroke: '#d97706', text: '예약됨' }; // amber
      case 'OCCUPIED':
        return { bg: '#fecaca', stroke: '#dc2626', text: '사용중' }; // red
      default:
        return { bg: '#f3f4f6', stroke: '#6b7280', text: '알 수 없음' };
    }
  };

  // Format time display
  const formatTime = (timeStr: string) => {
    return new Date(timeStr).toLocaleTimeString('ko-KR', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  // Get status label with time info
  const getStatusLabel = (room: Room) => {
    const colors = getStatusColors(room.status);
    let timeInfo = '';
    
    if (room.status === 'OCCUPIED' && room.current) {
      timeInfo = ` ~${formatTime(room.current.until)}`;
    } else if (room.status === 'RESERVED' && room.next) {
      timeInfo = ` ${formatTime(room.next.start)} 시작`;
    }
    
    return `${colors.text}${timeInfo}`;
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      {/* Header - Fixed */}
      <div className="flex-shrink-0 p-4 border-b bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900 mb-1">Desk & Room Booker</h1>
            <p className="text-sm text-gray-600">실시간 회의실·포커스룸 상태를 확인하고 예약하세요</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-sm text-gray-500">
              마지막 업데이트: {lastUpdate}
            </div>
            <button
              onClick={refreshAll}
              className="p-2 text-blue-500 hover:text-blue-700 hover:bg-blue-50 rounded-md transition-colors"
              title="새로고침"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
        
        {/* User Status */}
        {userStatus && (
          <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                {userStatus.focus_room && (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span className="text-sm font-medium text-gray-700">
                      포커스룸: {userStatus.focus_room.name}
                    </span>
                  </div>
                )}
                {userStatus.active_meeting_rooms.length > 0 && (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                    <span className="text-sm font-medium text-gray-700">
                      사용중: {userStatus.active_meeting_rooms.map(r => r.name).join(', ')}
                    </span>
                  </div>
                )}
                {userStatus.upcoming_meeting_rooms.length > 0 && (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
                    <span className="text-sm font-medium text-gray-700">
                      예약됨: {userStatus.upcoming_meeting_rooms.map(r => r.name).join(', ')}
                    </span>
                  </div>
                )}
                {!userStatus.focus_room && userStatus.active_meeting_rooms.length === 0 && userStatus.upcoming_meeting_rooms.length === 0 && (
                  <span className="text-sm text-gray-500">현재 사용 중인 공간이 없습니다</span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main Content - Flex Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Status List - Fixed width, scrollable */}
        <div className="w-90 flex-shrink-0 bg-white border-r overflow-hidden flex flex-col">
          <div className="p-4 border-b bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-800">전체 현황</h2>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {/* Meeting Rooms */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-1">회의실 (10개)</h3>
              <div className="space-y-1">
                {rooms.filter(r => r.type === 'MEETING').map(room => {
                  const colors = getStatusColors(room.status);
                  return (
                    <div 
                      key={room.roomId}
                      className="py-1.5 px-3 bg-white rounded border cursor-pointer hover:bg-gray-50 transition-colors"
                      onClick={() => handleRoomClick(room.roomId)}
                      style={{ borderLeftColor: colors.stroke, borderLeftWidth: '3px' }}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium text-gray-900">{room.name}</div>
                          <div className="text-xs text-gray-600">수용: {room.capacity}명</div>
                        </div>
                        <div className="text-right">
                          <div 
                            className="inline-block px-1.5 py-0.5 rounded text-xs font-medium"
                            style={{ backgroundColor: colors.bg, color: colors.stroke }}
                          >
                            {getStatusLabel(room)}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Focus Rooms */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-1">포커스룸 ({rooms.filter(r => r.type === 'FOCUS').length}개)</h3>
              <div className="space-y-1">
                {rooms.filter(r => r.type === 'FOCUS').map(room => {
                  const colors = getStatusColors(room.status);
                  return (
                    <div 
                      key={room.roomId}
                      className="py-1.5 px-3 bg-white rounded border cursor-pointer hover:bg-gray-50 transition-colors"
                      onClick={() => handleRoomClick(room.roomId)}
                      style={{ borderLeftColor: colors.stroke, borderLeftWidth: '3px' }}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium text-gray-900">{room.name}</div>
                          <div className="text-xs text-gray-600">1인실</div>
                        </div>
                        <div className="text-right">
                          <div 
                            className="inline-block px-1.5 py-0.5 rounded text-xs font-medium"
                            style={{ backgroundColor: colors.bg, color: colors.stroke }}
                          >
                            {getStatusLabel(room)}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            
            {/* Bottom spacing to match office map height */}
            <div className="h-16"></div>
          </div>
        </div>

        {/* SVG Interactive Map - Flexible, fixed height */}
        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="p-4 border-b bg-gray-50">
            <h2 className="text-lg font-semibold text-gray-800">오피스 맵</h2>
            
            {/* Legend */}
            <div className="flex items-center gap-6 mt-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-green-200 border border-green-500"></div>
                <span>사용 가능</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-amber-200 border border-amber-500"></div>
                <span>예약됨</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-red-200 border border-red-600"></div>
                <span>사용중</span>
              </div>
            </div>
          </div>

          <div className="flex-1 p-4 overflow-hidden">
            <div className="h-full bg-white rounded border overflow-hidden">
              {/* SVG Map */}
              <svg viewBox="0 0 960 450" className="w-full h-full">
                {/* Background */}
                <rect x="0" y="0" width="960" height="450" fill="#f9fafb" />
                
                {/* Meeting Rooms */}
                {OFFICE_LAYOUT.MEETING_ROOMS.map(layout => {
                  const room = rooms.find(r => r.roomId === layout.id);
                  const colors = room ? getStatusColors(room.status) : getStatusColors('AVAILABLE');
                  
            return (
                    <g key={layout.id} className="cursor-pointer" onClick={() => room && handleRoomClick(room.roomId)}>
                      <rect
                        x={layout.x}
                        y={layout.y}
                        width={layout.w}
                        height={layout.h}
                        fill={colors.bg}
                        stroke={colors.stroke}
                        strokeWidth="2"
                        rx="8"
                      />
                      <text
                        x={layout.x + layout.w/2}
                        y={layout.y + layout.h/2 - 5}
                        textAnchor="middle"
                        className="text-sm font-medium"
                        fill="#374151"
                      >
                        {layout.name}
                      </text>
                      <text
                        x={layout.x + layout.w/2}
                        y={layout.y + layout.h/2 + 15}
                        textAnchor="middle"
                        className="text-xs"
                        fill="#6b7280"
                      >
                        {room ? getStatusColors(room.status).text : '사용 가능'}
                      </text>
              </g>
            );
          })}

                {/* Focus Rooms */}
                {OFFICE_LAYOUT.FOCUS_ROOMS.map(layout => {
                  const room = rooms.find(r => r.roomId === layout.id);
                  const colors = room ? getStatusColors(room.status) : getStatusColors('AVAILABLE');
                  
              return (
                    <g key={layout.id} className="cursor-pointer" onClick={() => room && handleRoomClick(room.roomId)}>
                      <rect
                        x={layout.x}
                        y={layout.y}
                        width={layout.w}
                        height={layout.h}
                        fill={colors.bg}
                        stroke={colors.stroke}
                        strokeWidth="2"
                        rx="6"
                      />
                      <text
                        x={layout.x + layout.w/2}
                        y={layout.y + layout.h/2 - 5}
                        textAnchor="middle"
                        className="text-sm font-medium"
                        fill="#374151"
                      >
                        {layout.name}
                      </text>
                      <text
                        x={layout.x + layout.w/2}
                        y={layout.y + layout.h/2 + 15}
                        textAnchor="middle"
                        className="text-xs"
                        fill="#6b7280"
                      >
                        {room ? getStatusColors(room.status).text : '사용 가능'}
                      </text>
              </g>
            );
          })}
        </svg>
      </div>
          </div>
        </div>
      </div>

      {/* Popover for Room Details */}
      {showPopover && selectedRoom && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={closePopover}>
          <div className="bg-white rounded-lg p-6 w-96 max-w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">{selectedRoom.name}</h3>
              <button onClick={closePopover} className="text-gray-400 hover:text-gray-600">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
      </div>

            <div className="mb-4">
              <div className="text-sm text-gray-600 mb-2">현재 상태</div>
              <div 
                className="inline-block px-3 py-1 rounded text-sm font-medium"
                style={{ 
                  backgroundColor: getStatusColors(selectedRoom.status).bg, 
                  color: getStatusColors(selectedRoom.status).stroke 
                }}
              >
                {getStatusLabel(selectedRoom)}
          </div>
        </div>

        {selectedRoom.type === 'MEETING' ? (
          <MeetingRoomPopover
            room={selectedRoom}
            reservations={reservations}
            loading={loading}
            onClose={closePopover}
            onRefresh={fetchRoomsStatus}
            onRefreshUserStatus={refreshUserStatus}
          />
        ) : (
          <FocusRoomPopover
            room={selectedRoom}
            onClose={closePopover}
            onRefresh={fetchRoomsStatus}
            onRefreshUserStatus={refreshUserStatus}
          />
        )}
        </div>
      </div>
      )}
    </div>
  );
}

// Meeting Room Popover Component
function MeetingRoomPopover({ 
  room, 
  reservations, 
  loading, 
  onClose, 
  onRefresh,
  onRefreshUserStatus
}: { 
  room: Room; 
  reservations: Reservation[]; 
  loading: boolean;
  onClose: () => void;
  onRefresh: () => void;
  onRefreshUserStatus: () => void;
}) {
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [userStatus, setUserStatus] = useState<UserStatus | null>(null);

  // Fetch user status to check if user has reservations for this room
  useEffect(() => {
    const fetchUserStatus = async () => {
      try {
        const response = await fetch('/api/user/status');
        const data = await response.json();
        setUserStatus(data);
      } catch (error) {
        console.error('Failed to fetch user status:', error);
      }
    };
    fetchUserStatus();
  }, []);

  const handleReservation = async () => {
    if (!startTime || !endTime) return;
    
    setSubmitting(true);
    try {
      const response = await fetch(`/api/rooms/${room.roomId}/reservations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          start: startTime,
          end: endTime,
        }),
      });

      if (response.ok) {
        alert('예약이 완료되었습니다!');
        onRefresh();
        // Refresh user status to show new reservation
        onRefreshUserStatus();
        onClose();
      } else {
        const error = await response.json();
        alert(`예약 실패: ${error.error}`);
      }
    } catch (error) {
      alert('예약 중 오류가 발생했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelReservation = async (reservationId: number) => {
    if (!confirm('예약을 취소하시겠습니까?')) return;
    
    try {
      const response = await fetch(`/api/rooms/${room.roomId}/reservations/${reservationId}/cancel`, {
        method: 'POST',
      });

      if (response.ok) {
        alert('예약이 취소되었습니다!');
        onRefresh();
        // Refresh user status to remove cancelled reservation
        onRefreshUserStatus();
        onClose();
      } else {
        const error = await response.json();
        alert(`예약 취소 실패: ${error.error}`);
      }
    } catch (error) {
      alert('예약 취소 중 오류가 발생했습니다.');
    }
  };

  const handleCheckout = async () => {
    if (!confirm('회의실에서 체크아웃하시겠습니까?')) return;
    
    try {
      const response = await fetch(`/api/rooms/${room.roomId}/checkout`, {
        method: 'POST',
      });

      if (response.ok) {
        alert('체크아웃 완료!');
        onRefresh();
        // Refresh user status to remove checked out room
        onRefreshUserStatus();
        onClose();
      } else {
        const error = await response.json();
        alert(`체크아웃 실패: ${error.error}`);
      }
    } catch (error) {
      alert('체크아웃 중 오류가 발생했습니다.');
    }
  };

  return (
    <div>
      <div className="mb-4">
        <h4 className="font-medium mb-2">새 예약</h4>
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-600 mb-1">시작 시간</label>
            <input
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">종료 시간</label>
            <input
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm"
            />
          </div>
          <button
            onClick={handleReservation}
            disabled={!startTime || !endTime || submitting}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 text-sm"
          >
            {submitting ? '예약 중...' : '예약하기'}
          </button>
        </div>
      </div>

      <div>
        <h4 className="font-medium mb-2">내 예약</h4>
        {userStatus && (
          <div className="space-y-2 mb-4">
            {/* Active reservations */}
            {userStatus.active_meeting_rooms
              .filter(r => r.id === room.roomId)
              .map(reservation => (
                <div key={reservation.reservation_id} className="p-2 bg-red-50 border border-red-200 rounded text-sm">
                  <div className="font-medium text-red-800">
                    사용중: {new Date(reservation.start_time).toLocaleString()} ~ {new Date(reservation.end_time).toLocaleString()}
                  </div>
                  <button
                    onClick={() => handleCheckout()}
                    className="mt-1 px-2 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700"
                  >
                    체크아웃
                  </button>
                </div>
              ))}
            
            {/* Upcoming reservations */}
            {userStatus.upcoming_meeting_rooms
              .filter(r => r.id === room.roomId)
              .map(reservation => (
                <div key={reservation.reservation_id} className="p-2 bg-amber-50 border border-amber-200 rounded text-sm">
                  <div className="font-medium text-amber-800">
                    예약됨: {new Date(reservation.start_time).toLocaleString()} ~ {new Date(reservation.end_time).toLocaleString()}
                  </div>
                  <button
                    onClick={() => handleCancelReservation(reservation.reservation_id)}
                    className="mt-1 px-2 py-1 bg-amber-600 text-white text-xs rounded hover:bg-amber-700"
                  >
                    예약 취소
                  </button>
                </div>
              ))}
          </div>
        )}

        <h4 className="font-medium mb-2">전체 예약</h4>
        {loading ? (
          <p className="text-sm text-gray-500">로딩 중...</p>
        ) : reservations.length === 0 ? (
          <p className="text-sm text-gray-500">예약이 없습니다.</p>
        ) : (
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {reservations.map(reservation => (
              <div key={reservation.id} className="p-2 border rounded text-sm">
                <div className="font-medium">
                  {new Date(reservation.start_time).toLocaleString()} ~ {new Date(reservation.end_time).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Focus Room Popover Component
function FocusRoomPopover({ 
  room, 
  onClose, 
  onRefresh,
  onRefreshUserStatus
}: { 
  room: Room; 
  onClose: () => void;
  onRefresh: () => void;
  onRefreshUserStatus: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [userStatus, setUserStatus] = useState<UserStatus | null>(null);

  // Fetch user status to check if user has active focus room
  useEffect(() => {
    const fetchUserStatus = async () => {
      try {
        const response = await fetch('/api/user/status');
        const data = await response.json();
        setUserStatus(data);
      } catch (error) {
        console.error('Failed to fetch user status:', error);
      }
    };
    fetchUserStatus();
  }, []);

  const handleClaim = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/focus/${room.roomId}/claim`, {
        method: 'POST',
      });

      if (response.ok) {
        alert('포커스룸 사용을 시작했습니다! (2시간 타이머)');
        onRefresh();
        // Refresh user status to show new focus room
        onRefreshUserStatus();
        onClose();
      } else {
        const error = await response.json();
        alert(`사용 시작 실패: ${error.error}`);
      }
    } catch (error) {
      alert('요청 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleExtend = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/focus/${room.roomId}/extend`, {
        method: 'POST',
      });

      if (response.ok) {
        alert('30분 연장되었습니다!');
        onRefresh();
        // Refresh user status to update focus room info
        onRefreshUserStatus();
        onClose();
      } else {
        const error = await response.json();
        alert(`연장 실패: ${error.error}`);
      }
    } catch (error) {
      alert('요청 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleRelease = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/focus/${room.roomId}/release`, {
        method: 'POST',
      });

      if (response.ok) {
        alert('체크아웃 완료!');
        onRefresh();
        // Refresh user status to remove focus room
        onRefreshUserStatus();
        onClose();
      } else {
        const error = await response.json();
        alert(`체크아웃 실패: ${error.error}`);
      }
    } catch (error) {
      alert('요청 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* User's current focus room status */}
      {userStatus && userStatus.focus_room && (
        <div className="p-3 bg-green-50 border border-green-200 rounded">
          <h4 className="font-medium text-green-800 mb-1">현재 사용 중</h4>
          <p className="text-sm text-green-700">
            {userStatus.focus_room.name} - {new Date(userStatus.focus_room.start_time).toLocaleString()}부터 사용 중
          </p>
        </div>
      )}

      {room.status === 'AVAILABLE' ? (
        <button
          onClick={handleClaim}
          disabled={loading || (userStatus && userStatus.focus_room)}
          className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300"
        >
          {loading ? '처리 중...' : 
           userStatus && userStatus.focus_room ? '이미 사용 중' : '찜하기 (사용 시작)'}
        </button>
      ) : (
        <div className="space-y-2">
          <button
            onClick={handleExtend}
            disabled={loading}
            className="w-full px-4 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:bg-gray-300"
          >
            {loading ? '처리 중...' : '30분 연장'}
          </button>
          <button
            onClick={handleRelease}
            disabled={loading}
            className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-300"
          >
            {loading ? '처리 중...' : '체크아웃'}
          </button>
        </div>
      )}
      
      <p className="text-xs text-gray-500 text-center">
        {userStatus && userStatus.focus_room ? 
          '한 번에 하나의 포커스룸만 사용할 수 있습니다.' :
          room.status === 'AVAILABLE' 
            ? '빈자리입니다. 찜하기를 눌러 2시간 타이머로 사용을 시작하세요.'
            : '사용 중입니다. 연장하거나 체크아웃할 수 있습니다.'}
      </p>
    </div>
  );
}
