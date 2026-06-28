import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Polyline,
  CircleMarker,
  Tooltip,
  Pane,
  useMap,
} from "react-leaflet";

const API_URL = "http://localhost:8000";

const initialRoute = {
  route_name: "Маршрут с заходом в бухту золотой рог и выходом из него",
  points: [
    { latitude: 43.1005, longitude: 131.7875 },
    { latitude: 43.0955, longitude: 131.7985 },
    { latitude: 43.0895, longitude: 131.8105 },
    { latitude: 43.0835, longitude: 131.8225 },
    { latitude: 43.0785, longitude: 131.8335 },
    { latitude: 43.0715, longitude: 131.8435 },
    { latitude: 43.0770, longitude: 131.8515 },
    { latitude: 43.0810, longitude: 131.8595 },
    { latitude: 43.0870, longitude: 131.8675 },
    { latitude: 43.0955, longitude: 131.8755 },
    { latitude: 43.1100, longitude: 131.8865 },
    { latitude: 43.1030, longitude: 131.8835 },
    { latitude: 43.1005, longitude: 131.8815 },
    { latitude: 43.0915, longitude: 131.8775 },
    { latitude: 43.0825, longitude: 131.8765 },
    { latitude: 43.0745, longitude: 131.8805 },
    { latitude: 43.0675, longitude: 131.9000 },
    { latitude: 43.0605, longitude: 131.9120 },
    { latitude: 43.0540, longitude: 131.9275 },
    { latitude: 43.0480, longitude: 131.9375 },
    { latitude: 43.0425, longitude: 131.9485 },
  ],
};

function riskLevelRu(level) {
  if (level === "high") return "высокий";
  if (level === "medium") return "средний";
  if (level === "low") return "низкий";
  return "не определён";
}

function roleRu(role) {
  if (role === "admin") return "Администратор";
  if (role === "researcher") return "Исследователь";
  return "Пользователь";
}

function riskZoneStyle(feature) {
  const level = feature?.properties?.risk_level;

  if (level === "high") {
    return {
      color: "#dc2626",
      fillColor: "#ef4444",
      weight: 2,
      fillOpacity: 0.18,
    };
  }

  if (level === "medium") {
    return {
      color: "#d97706",
      fillColor: "#f59e0b",
      weight: 2,
      fillOpacity: 0.14,
    };
  }

  return {
    color: "#16a34a",
    fillColor: "#22c55e",
    weight: 2,
    fillOpacity: 0.1,
  };
}

function problemSegmentStyle(feature) {
  const level = feature?.properties?.risk_level;

  if (level === "high") {
    return {
      color: "#b91c1c",
      weight: 8,
      opacity: 1,
    };
  }

  if (level === "medium") {
    return {
      color: "#f97316",
      weight: 7,
      opacity: 0.95,
    };
  }

  return {
    color: "#16a34a",
    weight: 6,
    opacity: 0.95,
  };
}

function trajectoryStyle() {
  return {
    color: "#64748b",
    weight: 2,
    opacity: 0.32,
    dashArray: "8 8",
  };
}

function FitMapToData({ routePositions, riskZones, trajectories }) {
  const map = useMap();

  useEffect(() => {
    const points = [];

    routePositions.forEach((point) => points.push(point));

    if (riskZones?.features) {
      riskZones.features.forEach((feature) => {
        const geometry = feature.geometry;

        if (geometry?.type === "Polygon") {
          geometry.coordinates[0].forEach(([lng, lat]) => {
            points.push([lat, lng]);
          });
        }

        if (geometry?.type === "MultiPolygon") {
          geometry.coordinates.forEach((polygon) => {
            polygon[0].forEach(([lng, lat]) => {
              points.push([lat, lng]);
            });
          });
        }
      });
    }

    if (trajectories?.features) {
      trajectories.features.forEach((feature) => {
        const geometry = feature.geometry;

        if (geometry?.type === "LineString") {
          geometry.coordinates.forEach(([lng, lat]) => {
            points.push([lat, lng]);
          });
        }
      });
    }

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [map, routePositions, riskZones, trajectories]);

  return null;
}

function App() {
  const [status, setStatus] = useState("Интерфейс готов к работе");
  const [file, setFile] = useState(null);

  const [token, setToken] = useState(
    () => localStorage.getItem("marine_dss_token") || ""
  );

  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const savedUser = localStorage.getItem("marine_dss_user");
      return savedUser ? JSON.parse(savedUser) : null;
    } catch {
      return null;
    }
  });

  const [loginForm, setLoginForm] = useState({
    username: "",
    password: "",
  });

  const [loginError, setLoginError] = useState("");

  const [trajectories, setTrajectories] = useState(null);
  const [heatmap, setHeatmap] = useState([]);
  const [riskZones, setRiskZones] = useState(null);

  const [routeText, setRouteText] = useState(
    JSON.stringify(initialRoute, null, 2)
  );
  const [routeEvaluation, setRouteEvaluation] = useState(null);

  const [reports, setReports] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);

  const [layers, setLayers] = useState({
    trajectories: true,
    heatmap: true,
    riskZones: true,
    route: true,
    problemSegments: true,
  });

    const isAdmin = currentUser?.role === "admin";
    const isResearcher = currentUser?.role === "researcher";

    const canManageData = isAdmin;
    const canViewAuditLogs = isAdmin;
    const canViewAnalyticalLayers = isResearcher;
    const canPlanRoute = isResearcher;
    const canEvaluateRoute = isResearcher;
    const canCreateReport = isResearcher;

  function clearLoginForm() {
    setLoginForm({
      username: "",
      password: "",
    });
  }

  function clearMapLayers() {
    setTrajectories(null);
    setHeatmap([]);
    setRiskZones(null);
    setRouteEvaluation(null);
  }

  function clearAnalyticalLayers() {
    setTrajectories(null);
    setHeatmap([]);
    setRiskZones(null);

    setStatus("Аналитические слои очищены с карты.");
  }

  function logout(message = "Вы вышли из системы") {
    localStorage.removeItem("marine_dss_token");
    localStorage.removeItem("marine_dss_user");

    setToken("");
    setCurrentUser(null);
    setReports([]);
    setAuditLogs([]);
    clearMapLayers();
    setLoginError("");
    clearLoginForm();
    setStatus(message);
  }

  async function apiRequest(path, options = {}, authToken = token) {
    const headers = new Headers(options.headers || {});

    if (authToken) {
      headers.set("Authorization", `Bearer ${authToken}`);
    }

    let response;

    try {
      response = await fetch(`${API_URL}${path}`, {
        ...options,
        headers,
      });
    } catch (error) {
      throw new Error(
        `Не удалось подключиться к backend (${API_URL}). Проверьте, что FastAPI запущен на порту 8000. Технически: ${
          error.message || "Failed to fetch"
        }`
      );
    }

    let data = null;
    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      if (response.status === 401 && path !== "/api/auth/login") {
        logout("Выполните вход в систему.");
      }

      const detail =
        typeof data === "string"
          ? data
          : Array.isArray(data.detail)
            ? JSON.stringify(data.detail)
            : data.detail || "Ошибка запроса";

      const requestError = new Error(detail);
      requestError.status = response.status;
      throw requestError;
    }

    return data;
  }

  function toggleLayer(layerName) {
    setLayers((previous) => ({
      ...previous,
      [layerName]: !previous[layerName],
    }));
  }

  function clearEvaluation() {
    setRouteEvaluation(null);
    setStatus("Оценка маршрута очищена. Можно задать новый маршрут.");
  }

  const routePositions = useMemo(() => {
    if (routeEvaluation?.route?.geometry?.coordinates) {
      return routeEvaluation.route.geometry.coordinates.map(([lng, lat]) => [
        lat,
        lng,
      ]);
    }

    try {
      const route = JSON.parse(routeText);
      return route.points.map((point) => [point.latitude, point.longitude]);
    } catch {
      return [];
    }
  }, [routeText, routeEvaluation]);

  async function checkBackend() {
    try {
      const health = await apiRequest("/health", {}, "");
      const dbHealth = await apiRequest("/db-health", {}, "");

      setStatus(
        `Backend: ${health.status}; БД: ${dbHealth.database}; PostGIS: ${dbHealth.postgis_version}`
      );
    } catch (error) {
      setStatus(`Ошибка проверки backend: ${error.message}`);
    }
  }

  async function validateSession(authToken = token) {
    try {
      const result = await apiRequest("/api/auth/me", {}, authToken);
      const user = result.user;

      setCurrentUser(user);
      localStorage.setItem("marine_dss_user", JSON.stringify(user));

      if (user.role === "researcher") {
        await loadReports(authToken);
      }
    } catch {
      logout("Выполните вход в систему.");
    }
  }

  async function login(event) {
    event.preventDefault();

    const username = loginForm.username.trim();
    const password = loginForm.password;

    setLoginError("");

    if (!username) {
      setLoginError("Введите логин");
      return;
    }

    if (!password) {
      setLoginError("Введите пароль");
      return;
    }

    try {
      const result = await apiRequest(
        "/api/auth/login",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username,
            password,
          }),
        },
        ""
      );

      localStorage.setItem("marine_dss_token", result.access_token);
      localStorage.setItem("marine_dss_user", JSON.stringify(result.user));

      setToken(result.access_token);
      setCurrentUser(result.user);
      clearLoginForm();

      setStatus(
        `Вход выполнен: ${result.user.username}, роль: ${roleRu(
          result.user.role
        )}`
      );

      if (result.user.role === "researcher") {
        await loadReports(result.access_token);
      }
    } catch (error) {
      const message = String(error.message || "").toLowerCase();

      if (
        message.includes("invalid") ||
        message.includes("incorrect") ||
        message.includes("unauthorized") ||
        message.includes("401") ||
        message.includes("недейств") ||
        message.includes("невер") ||
        message.includes("unauthenticated")
      ) {
        setLoginError("Некорректный логин или пароль");
        return;
      }

      setLoginError(error.message || "Ошибка входа в систему");
    }
  }

  async function uploadAisFile() {
    if (!canManageData) {
      setStatus("Недостаточно прав: загрузка АИС-данных доступна только администратору");
      return;
    }

    if (!file) {
      setStatus("Сначала выберите CSV-файл");
      return;
    }

    const authToken = localStorage.getItem("marine_dss_token") || token;

    if (!authToken) {
      setStatus("Ошибка загрузки: пользователь не авторизован");
      return;
    }

    try {
      setStatus("Загрузка и очистка АИС-данных...");

      const formData = new FormData();
      formData.append("file", file, file.name);

      const result = await apiRequest(
        "/api/ais/upload",
        {
          method: "POST",
          body: formData,
        },
        authToken
      );

      clearMapLayers();
      setAuditLogs([]);

      setStatus(
        `АИС-файл загружен. Файл: ${result.filename}. Строк всего: ${
          result.statistics?.initial_rows ?? "не указано"
        }. Корректных строк: ${
          result.statistics?.valid_rows ?? "не указано"
        }. Сохранено строк: ${
          result.statistics?.saved_rows ?? "не указано"
        }. Старые аналитические слои очищены. Отчёты сохранены.`
      );
    } catch (error) {
      setStatus(`Ошибка загрузки АИС-файла: ${error.message}`);
    }
  }

  async function buildTrajectories() {
    if (!canManageData) {
      setStatus("Недостаточно прав: формирование траекторий доступно только администратору");
      return;
    }

    const authToken = localStorage.getItem("marine_dss_token") || token;

    if (!authToken) {
      setStatus("Ошибка построения траекторий: пользователь не авторизован");
      return;
    }

    try {
      setStatus("Формирование траекторий судов...");

      const result = await apiRequest(
        "/api/ais/build-trajectories",
        {
          method: "POST",
        },
        authToken
      );

      setStatus(
        `Траектории сформированы. Количество: ${result.trajectories_count}`
      );

      await loadTrajectories(authToken);
    } catch (error) {
      setStatus(`Ошибка построения траекторий: ${error.message}`);
    }
  }

  async function loadTrajectories(authToken = token) {
    try {
      const result = await apiRequest(
        "/api/ais/trajectories?limit=5000",
        {},
        authToken
      );

      setTrajectories(result);
      setStatus(`Траектории загружены на карту. Количество: ${result.count}`);
    } catch (error) {
      if (error.status === 401) {
        return;
      }

      setStatus(`Ошибка загрузки траекторий: ${error.message}`);
    }
  }

  async function buildHeatmap() {
    if (!canManageData) {
      setStatus("Недостаточно прав: построение тепловой карты доступно только администратору");
      return;
    }

    const authToken = localStorage.getItem("marine_dss_token") || token;

    if (!authToken) {
      setStatus("Ошибка построения тепловой карты: пользователь не авторизован");
      return;
    }

    try {
      setStatus("Построение тепловой карты...");

      try {
        const result = await apiRequest(
          "/api/analytics/build-heatmap?cell_size=0.004&max_cells=7000",
          {
            method: "POST",
          },
          authToken
        );

        setStatus(
          `Тепловая карта сформирована. Ячеек: ${result.cells_count ?? result.count ?? 0}.`
        );
      } catch (error) {
        const message = String(error.message || "").toLowerCase();

        if (!message.includes("not found") && !message.includes("404")) {
          throw error;
        }

        // Совместимость со старой версией backend:
        // если отдельного POST /build-heatmap нет, GET /heatmap сам построит слой.
      }

      await loadHeatmap(authToken);
    } catch (error) {
      setStatus(`Ошибка построения тепловой карты: ${error.message}`);
    }
  }

  async function loadHeatmap(authToken = token) {
    try {
      const result = await apiRequest(
        "/api/analytics/heatmap?cell_size=0.004&max_cells=7000",
        {},
        authToken
      );

      setHeatmap(result.heatmap || []);
      setStatus(`Тепловая карта отображена. Ячеек: ${result.count}`);
    } catch (error) {
      if (error.status === 401) {
        return;
      }

      setStatus(`Ошибка загрузки тепловой карты: ${error.message}`);
    }
  }

  async function buildRiskZones() {
    if (!canManageData) {
      setStatus("Недостаточно прав: формирование зон риска доступно только администратору");
      return;
    }

    const authToken = localStorage.getItem("marine_dss_token") || token;

    if (!authToken) {
      setStatus("Ошибка построения зон риска: пользователь не авторизован");
      return;
    }

    try {
      setStatus("Формирование зон риска...");

      const result = await apiRequest(
        "/api/analytics/build-risk-zones?cell_size=0.004&low_threshold=4&medium_threshold=60&high_threshold=300&max_zones=7000",
        {
          method: "POST",
        },
        authToken
      );

      setStatus(
        `Зоны риска сформированы. Всего: ${result.zones_count}; low: ${result.low_zones_count}; medium: ${result.medium_zones_count}; high: ${result.high_zones_count}. Буфер фарватера: ${result.corridor_buffer_m ?? 450} м.`
      );

      await loadRiskZones(authToken);
    } catch (error) {
      setStatus(`Ошибка построения зон риска: ${error.message}`);
    }
  }

  async function loadRiskZones(authToken = token) {
    try {
      const result = await apiRequest(
        "/api/analytics/risk-zones",
        {},
        authToken
      );

      setRiskZones(result);
      setStatus(`Зоны риска загружены на карту. Количество: ${result.count}`);
    } catch (error) {
      if (error.status === 401) {
        return;
      }

      setStatus(`Ошибка загрузки зон риска: ${error.message}`);
    }
  }

  async function evaluateRoute() {
    if (!canEvaluateRoute) {
      setStatus("Недостаточно прав: оценка маршрута доступна только исследователю");
      return;
    }

    try {
      const route = JSON.parse(routeText);

      if (!route.points || route.points.length < 2) {
        setStatus("Ошибка оценки маршрута: маршрут должен содержать минимум две точки");
        return;
      }

      const result = await apiRequest("/api/dss/evaluate-route", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(route),
      });

      setRouteEvaluation(result);
      setStatus(
        `Маршрут оценён. Риск: ${
          result.risk_summary.risk_score
        }/100, уровень: ${riskLevelRu(result.risk_summary.risk_level)}`
      );
    } catch (error) {
      setStatus(`Ошибка оценки маршрута: ${error.message}`);
    }
  }

  async function createRouteReport() {
    if (!canCreateReport) {
      setStatus("Недостаточно прав: формирование отчёта доступно только исследователю");
      return;
    }

    try {
      const route = JSON.parse(routeText);

      const result = await apiRequest("/api/reports/route-report", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(route),
      });

      setStatus(
        `Отчёт сформирован. ID: ${result.report_id}; риск: ${result.risk_score}`
      );

      await loadReports();
    } catch (error) {
      setStatus(`Ошибка формирования отчёта: ${error.message}`);
    }
  }

  async function loadReports(authToken = token) {
    if (!canCreateReport && !authToken) {
      return;
    }

    try {
      const result = await apiRequest("/api/reports", {}, authToken);
      setReports(result.reports || []);
      setStatus(`Список отчётов загружен. Количество: ${result.count}`);
    } catch (error) {
      setStatus(`Ошибка загрузки отчётов: ${error.message}`);
    }
  }

  async function loadAuditLogs() {
    if (!canViewAuditLogs) {
      setStatus("Недостаточно прав: журнал действий доступен только администратору");
      return;
    }

    try {
      const result = await apiRequest("/api/auth/audit-logs?limit=20");
      setAuditLogs(result.logs || []);
      setStatus(`Журнал действий загружен. Записей: ${result.count}`);
    } catch (error) {
      setStatus(`Ошибка загрузки журнала действий: ${error.message}`);
    }
  }

  async function exportReport(reportId) {
    if (!canCreateReport) {
      setStatus("Недостаточно прав: экспорт отчёта доступен только исследователю");
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/reports/${reportId}/export-txt`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error("Не удалось экспортировать отчёт");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `route_report_${reportId}.txt`;
      document.body.appendChild(link);
      link.click();

      link.remove();
      window.URL.revokeObjectURL(url);

      setStatus(`Отчёт ID ${reportId} экспортирован в TXT.`);
    } catch (error) {
      setStatus(`Ошибка экспорта отчёта: ${error.message}`);
    }
  }

  useEffect(() => {
    checkBackend();

    if (token) {
      validateSession(token);
    }
  }, []);

  const riskSummary = routeEvaluation?.risk_summary;

  if (!token || !currentUser) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-header">
            <h1>Marine DSS</h1>
            <p>
              Система поддержки принятия решений для безопасности движения
              морских судов
            </p>
          </div>

          <form className="login-form" onSubmit={login} autoComplete="off">
            <h2>Вход в систему</h2>

            <label>
              Логин
              <input
                type="text"
                value={loginForm.username}
                autoComplete="off"
                onChange={(event) =>
                  setLoginForm((previous) => ({
                    ...previous,
                    username: event.target.value,
                  }))
                }
              />
            </label>

            <label>
              Пароль
              <input
                type="password"
                value={loginForm.password}
                autoComplete="new-password"
                onChange={(event) =>
                  setLoginForm((previous) => ({
                    ...previous,
                    password: event.target.value,
                  }))
                }
              />
            </label>

            {loginError && <div className="login-error">{loginError}</div>}

            <button className="primary-blue" type="submit">
              Войти
            </button>
          </form>

          <div className="login-status">
            <strong>Статус:</strong> {status}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>
            Система поддержки принятия решений для безопасности движения морских
            судов
          </h1>
          <p>
            Анализ ретроспективных данных АИС • маршруты • зоны риска •
            отчётность
          </p>
        </div>

        <div className="topbar-actions">
          <span className={`role-chip ${currentUser.role}`}>
            {roleRu(currentUser.role)}
          </span>
          <button onClick={() => logout()}>Выйти</button>
        </div>
      </header>

      <div className={`workspace ${isAdmin ? "admin-workspace" : "researcher-workspace"}`}>
        <aside className="sidebar">
          <h2>Разделы системы</h2>

          {isAdmin && (
            <>
              <div className="nav-button active">Загрузка АИС-данных</div>
              <div className="nav-button">Обработка и очистка данных</div>
              <div className="nav-button">Формирование траекторий</div>
              <div className="nav-button">Построение тепловой карты</div>
              <div className="nav-button">Формирование зон риска</div>
              <div className="nav-button">Журнал действий</div>
            </>
          )}

          {isResearcher && (
            <>
              <div className="nav-button active">Просмотр аналитических слоёв</div>
              <div className="nav-button">Задание маршрута</div>
              <div className="nav-button">Оценка маршрута</div>
              <div className="nav-button">Проблемные сегменты</div>
              <div className="nav-button">Рекомендации</div>
              <div className="nav-button">Отчёт</div>
            </>
          )}



          {canManageData && (
            <div className="side-section">
              <h3>Управление АИС-данными</h3>
              <input
                type="file"
                accept=".csv"
                onChange={(event) => setFile(event.target.files[0])}
              />
              <button onClick={uploadAisFile}>Загрузить и очистить CSV</button>
              <button onClick={buildTrajectories}>
                Сформировать траектории судов
              </button>
              <button onClick={buildHeatmap}>Построить тепловую карту</button>
              <button onClick={buildRiskZones}>Сформировать зоны риска</button>
            </div>
          )}

          {canViewAnalyticalLayers && (
            <div className="side-section">
              <h3>Просмотр аналитических слоёв</h3>
              <button onClick={() => loadTrajectories()}>Показать траектории</button>
              <button onClick={() => loadHeatmap()}>Показать тепловую карту</button>
              <button onClick={() => loadRiskZones()}>Показать зоны риска</button>
              <button onClick={clearAnalyticalLayers}>Очистить слои</button>
            </div>
          )}

          {canViewAnalyticalLayers && (
            <div className="side-section">
              <h3>Слои карты</h3>

              <label className="layer-toggle">
                <input
                  type="checkbox"
                  checked={layers.trajectories}
                  onChange={() => toggleLayer("trajectories")}
                />
                <span className="layer-line trajectory"></span>
                Исторические траектории
              </label>

              <label className="layer-toggle">
                <input
                  type="checkbox"
                  checked={layers.heatmap}
                  onChange={() => toggleLayer("heatmap")}
                />
                <span className="layer-dot heatmap"></span>
                Ячейки плотности движения
              </label>

              <label className="layer-toggle">
                <input
                  type="checkbox"
                  checked={layers.riskZones}
                  onChange={() => toggleLayer("riskZones")}
                />
                <span className="layer-box risk"></span>
                Зоны риска
              </label>

              {canPlanRoute && (
                <>
                  <label className="layer-toggle">
                    <input
                      type="checkbox"
                      checked={layers.route}
                      onChange={() => toggleLayer("route")}
                    />
                    <span className="layer-line route"></span>
                    Планируемый маршрут
                  </label>

                  <label className="layer-toggle">
                    <input
                      type="checkbox"
                      checked={layers.problemSegments}
                      onChange={() => toggleLayer("problemSegments")}
                    />
                    <span className="layer-line segment"></span>
                    Сегменты риска
                  </label>

                  <button onClick={clearEvaluation}>Очистить оценку</button>
                </>
              )}
            </div>
          )}

          {canCreateReport && (
            <div className="side-section">
              <h3>Отчётность</h3>
              <button className="primary-dark" onClick={createRouteReport}>
                Сформировать отчёт
              </button>
              <button onClick={() => loadReports()}>
                Обновить список отчётов
              </button>
            </div>
          )}

          {canViewAuditLogs && (
            <div className="side-section">
              <h3>Администрирование</h3>
              <button onClick={loadAuditLogs}>Показать журнал действий</button>
            </div>
          )}
        </aside>

        <main className="main">
          <section className="map-card">
            <div className="card-header">
              <div>
                <h2>Интерактивная карта маршрута и зон риска</h2>
                <p>
                  Отображение траекторий, тепловой карты, зон риска и маршрута
                </p>
              </div>

              <div className="legend">
                <span>
                  <i className="legend-box high"></i> зона высокого риска
                </span>
                <span>
                  <i className="legend-box medium"></i> зона среднего риска
                </span>
                <span>
                  <i className="legend-box low"></i> зона низкого риска
                </span>
                {canPlanRoute && (
                  <span>
                    <i className="legend-line route"></i> маршрут
                  </span>
                )}
                <span>
                  <i className="legend-line trajectory"></i> историческая
                  траектория
                </span>
                <span>
                  <i className="legend-dot heatmap"></i> ячейка heatmap
                </span>
              </div>
            </div>

            <div className="map-wrapper">
              <MapContainer
                center={[43.07, 131.90]}
                zoom={11}
                scrollWheelZoom={true}
                attributionControl={false}
                className="leaflet-map"
              >
                <TileLayer
                  attribution=""
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <FitMapToData
                  routePositions={canPlanRoute ? routePositions : []}
                  riskZones={riskZones}
                  trajectories={trajectories}
                />

                {layers.trajectories && trajectories?.features?.length > 0 && (
                  <Pane name="trajectories-pane" style={{ zIndex: 350 }}>
                    <GeoJSON
                      key={`traj-${trajectories.count}`}
                      data={trajectories}
                      style={trajectoryStyle}
                      onEachFeature={(feature, layer) => {
                        layer.bindTooltip(
                          `Историческая траектория судна MMSI: ${feature.properties.mmsi}`
                        );
                      }}
                    />
                  </Pane>
                )}

                {layers.riskZones && riskZones?.features?.length > 0 && (
                  <Pane name="risk-zones-pane" style={{ zIndex: 420 }}>
                    <GeoJSON
                      key={`risk-${riskZones.count}-${JSON.stringify(
                        riskZones.features.map((f) => f.properties.id)
                      )}`}
                      data={riskZones}
                      style={riskZoneStyle}
                      onEachFeature={(feature, layer) => {
                        layer.bindTooltip(
                          `Зона риска: ${riskLevelRu(
                            feature.properties.risk_level
                          )}\nОценка: ${feature.properties.risk_score}\nАИС-точек: ${feature.properties.points_count}`
                        );
                      }}
                    />
                  </Pane>
                )}

                {layers.heatmap && heatmap.length > 0 && (
                  <Pane name="heatmap-pane" style={{ zIndex: 500 }}>
                    {heatmap
                      .filter((point) => point.points_count >= 4)
                      .map((point, index) => (
                      <CircleMarker
                        key={`heat-${index}`}
                        center={[point.latitude, point.longitude]}
                        radius={5 + point.intensity * 11}
                        pathOptions={{
                          color: "#7c3aed",
                          fillColor: "#7c3aed",
                          fillOpacity: 0.18,
                          weight: 1,
                        }}
                      >
                        <Tooltip>
                          Ячейка тепловой карты
                          <br />
                          Точек: {point.points_count}
                          <br />
                          Интенсивность: {point.intensity}
                        </Tooltip>
                      </CircleMarker>
                    ))}
                  </Pane>
                )}

                {canPlanRoute && layers.route && routePositions.length >= 2 && (
                  <Pane name="route-pane" style={{ zIndex: 620 }}>
                    <Polyline
                      positions={routePositions}
                      pathOptions={{
                        color: "#2563eb",
                        weight: 6,
                        opacity: 0.85,
                      }}
                    />

                    {routePositions.map((position, index) => (
                      <CircleMarker
                        key={`route-point-${index}`}
                        center={position}
                        radius={5}
                        pathOptions={{
                          color: "#1d4ed8",
                          fillColor: "#ffffff",
                          fillOpacity: 1,
                          weight: 2,
                        }}
                      >
                        <Tooltip>{`W${index + 1}`}</Tooltip>
                      </CircleMarker>
                    ))}
                  </Pane>
                )}

                {canEvaluateRoute &&
                  layers.problemSegments &&
                  routeEvaluation?.problem_segments?.features?.length > 0 && (
                    <Pane name="segments-pane" style={{ zIndex: 700 }}>
                      <GeoJSON
                        key={`segments-${routeEvaluation.risk_summary.risk_score}`}
                        data={routeEvaluation.problem_segments}
                        style={problemSegmentStyle}
                        onEachFeature={(feature, layer) => {
                          layer.bindTooltip(
                            `Сегмент риска: ${riskLevelRu(
                              feature.properties.risk_level
                            )}\nДлина: ${feature.properties.length_m} м\nОценка: ${feature.properties.risk_score}`
                          );
                        }}
                      />
                    </Pane>
                  )}
              </MapContainer>
            </div>
          </section>

          {isAdmin && (
            <section className="cards-row admin-summary-row">
              <div className="info-card">
                <h3>Подготовленные АИС-данные</h3>
                <strong>{trajectories?.count ?? 0} траекторий</strong>
                <p>Количество сформированных исторических траекторий после загрузки CSV.</p>
              </div>

              <div className="info-card">
                <h3>Карта плотности движения</h3>
                <strong>{heatmap.length} ячеек</strong>
                <p>Ячейки показывают участки наибольшей концентрации ретроспективных АИС-сообщений.</p>
              </div>

              <div className="info-card">
                <h3>Зоны навигационного риска</h3>
                <strong>{riskZones?.count ?? 0} зон</strong>
                <p>Зоны рассчитываются по плотности движения и используются для оценки маршрута.</p>
              </div>
            </section>
          )}

          {canPlanRoute && (
            <section className="route-card">
              <div className="card-header">
                <div>
                  <h2>Задание маршрута</h2>
                  <p>
                    Задайте маршрут вручную в формате JSON: укажите название
                    маршрута и последовательность путевых точек.
                  </p>
                </div>
              </div>

              <textarea
                value={routeText}
                onChange={(event) => setRouteText(event.target.value)}
                spellCheck={false}
              />

              <div className="route-actions">
                <button className="primary-blue" onClick={evaluateRoute}>
                  Оценить риск маршрута
                </button>
              </div>
            </section>
          )}

          {canEvaluateRoute && (
            <section className="cards-row">
              <div className="info-card">
                <h3>Маршрут</h3>
                <strong>{routePositions.length} точек</strong>
                <p>
                  {riskSummary
                    ? `${riskSummary.route_length_m} м`
                    : "Маршрут готов к оценке"}
                </p>
              </div>

              <div className="info-card">
                <h3>Сегменты риска</h3>
                <strong>{riskSummary?.intersections_count ?? 0}</strong>
                <p>
                  high: {riskSummary?.high_segments_count ?? 0}, medium: {" "}
                  {riskSummary?.medium_segments_count ?? 0}, low: {" "}
                  {riskSummary?.low_segments_count ?? 0}
                </p>
              </div>

              <div className="info-card">
                <h3>Аналитические слои</h3>
                <strong>Heatmap + зоны риска</strong>
                <p>
                  heatmap: {heatmap.length}, зоны: {riskZones?.count ?? 0}
                </p>
              </div>

              <div className="info-card">
                <h3>Экспорт</h3>
                <strong>TXT</strong>
                <p>Отчёт сохраняется в БД</p>
              </div>
            </section>
          )}

          {canViewAuditLogs && auditLogs.length > 0 && (
            <section className="reports-card">
              <div className="card-header">
                <div>
                  <h2>Журнал действий пользователей</h2>
                  <p>Фиксация операций администратора и исследователя</p>
                </div>
                <button onClick={loadAuditLogs}>Обновить</button>
              </div>

              <div className="reports-list">
                {auditLogs.map((log) => (
                  <div className="report-item" key={log.id}>
                    <div>
                      <strong>{log.action}</strong>
                      <p>
                        {log.username || "system"} • {roleRu(log.role)} • {" "}
                        {log.created_at}
                      </p>
                      {log.details && <p>{log.details}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {canCreateReport && (
            <section className="reports-card">
              <div className="card-header">
                <div>
                  <h2>Сформированные отчёты</h2>
                  <p>Отчёты сохраняются в хранилище данных</p>
                </div>
                <button onClick={() => loadReports()}>Обновить</button>
              </div>

              {reports.length === 0 ? (
                <p className="muted">Отчёты пока не сформированы.</p>
              ) : (
                <div className="reports-list">
                  {reports.map((report) => (
                    <div className="report-item" key={report.id}>
                      <div>
                        <strong>{report.title}</strong>
                        <p>
                          Риск: {riskLevelRu(report.risk_level)} • {" "}
                          {report.risk_score}/100 • ID: {report.id}
                        </p>
                      </div>
                      <button onClick={() => exportReport(report.id)}>
                        Экспорт TXT
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </main>

        {canEvaluateRoute && (
          <aside className="risk-panel">
            <h2>Оценка риска маршрута</h2>

            <div className={`risk-badge ${riskSummary?.risk_level || "low"}`}>
              {riskSummary ? riskLevelRu(riskSummary.risk_level) : "нет оценки"}
            </div>

            <div className={`risk-score ${riskSummary?.risk_level || "low"}`}>
              <span>{riskSummary?.risk_score ?? 0}</span>
              <small>/ 100</small>
            </div>

            <div className="progress">
              <div
                style={{
                  width: `${riskSummary?.risk_score ?? 0}%`,
                }}
              ></div>
            </div>

            <h3>Факторы риска</h3>

            <div className="factor">
              <span>Доля маршрута в зонах риска</span>
              <strong>{riskSummary?.risky_length_percent ?? 0}%</strong>
            </div>

            <div className="factor">
              <span>Пересечения с зонами риска</span>
              <strong>{riskSummary?.intersections_count ?? 0}</strong>
            </div>

            <div className="factor">
              <span>Сегменты высокого риска</span>
              <strong>{riskSummary?.high_segments_count ?? 0}</strong>
            </div>

            <div className="factor">
              <span>Длина маршрута в зонах риска</span>
              <strong>{riskSummary?.risky_length_m ?? 0} м</strong>
            </div>

            <h3>Рекомендации</h3>

            <ul className="recommendations">
              {routeEvaluation?.recommendations?.length > 0 ? (
                routeEvaluation.recommendations.map((item, index) => (
                  <li key={index}>{item}</li>
                ))
              ) : (
                <li>Выполните оценку маршрута для получения рекомендаций.</li>
              )}
            </ul>

            <button className="primary-blue" onClick={evaluateRoute}>
              Пересчитать
            </button>

            <button onClick={createRouteReport}>Сформировать отчёт</button>
          </aside>
        )}
      </div>

      <footer className="statusbar">
        <strong>Статус:</strong> {status}
      </footer>
    </div>
  );
}

export default App;
