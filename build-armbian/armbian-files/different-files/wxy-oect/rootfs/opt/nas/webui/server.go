package main

// WXY-OECT NAS Web UI Manager
// Lightweight Go server: auto-exits after 50s idle, ~10MB binary
// Compile: GOARCH=arm64 GOOS=linux go build -ldflags="-s -w" server.go

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"time"
)

const idleTimeout = 50 * time.Second

var (
	lastActivity time.Time
	mu           sync.Mutex
	shutdownOnce sync.Once
)

func markActive() {
	mu.Lock()
	lastActivity = time.Now()
	mu.Unlock()
}

func isIdle() bool {
	mu.Lock()
	defer mu.Unlock()
	return time.Since(lastActivity) > idleTimeout
}

func runCmd(cmd string, args ...string) (string, error) {
	c := exec.Command(cmd, args...)
	out, err := c.CombinedOutput()
	if err != nil && !strings.Contains(string(out), "already") {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

func handleIndex(w http.ResponseWriter, r *http.Request) {
	markActive()
	http.ServeFile(w, r, "/opt/nas/webui/index.html")
}

func handleCSS(w http.ResponseWriter, r *http.Request) {
	markActive()
	http.ServeFile(w, r, "/opt/nas/webui/style.css")
}

func handleJS(w http.ResponseWriter, r *http.Request) {
	markActive()
	http.ServeFile(w, r, "/opt/nas/webui/app.js")
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	markActive()
	status := map[string]interface{}{
		"uptime":   getUptime(),
		"cpu":      getCPUUsage(),
		"memory":   getMemoryInfo(),
		"storage":  getStorageInfo(),
		"network":  getNetworkInfo(),
		"services": getServiceStatus(),
	}
	writeJSON(w, status)
}

func handleRestart(w http.ResponseWriter, r *http.Request) {
	markActive()
	if r.Method != "POST" {
		http.Error(w, "method not allowed", 405)
		return
	}
	go func() {
		time.Sleep(1 * time.Second)
		runCmd("reboot")
	}()
	writeJSON(w, map[string]string{"status": "restarting"})
}

func handleService(w http.ResponseWriter, r *http.Request) {
	markActive()
	name := r.URL.Query().Get("service")
	action := r.URL.Query().Get("action")
	if name == "" || action == "" {
		http.Error(w, "missing service or action", 400)
		return
	}
	err := runCmd("systemctl", action, name)
	if err != nil {
		writeJSON(w, map[string]string{"status": "error", "error": err.Error()})
		return
	}
	writeJSON(w, map[string]string{"status": "ok", "service": name, "action": action})
}

func handleDiskMount(w http.ResponseWriter, r *http.Request) {
	markActive()
	if r.Method != "POST" {
		http.Error(w, "method not allowed", 405)
		return
	}
	runCmd("mount", "-a")
	devices := getDiskDevices()
	writeJSON(w, map[string]interface{}{"status": "ok", "devices": devices})
}

func getUptime() string {
	data, _ := ioutil.ReadFile("/proc/uptime")
	if len(data) == 0 {
		return "unknown"
	}
	secs, _ := strconv.ParseFloat(strings.TrimSpace(string(data)), 64)
	h := int(secs) / 3600
	m := (int(secs) % 3600) / 60
	return fmt.Sprintf("%dh %dm", h, m)
}

func getCPUUsage() string {
	load, _ := ioutil.ReadFile("/proc/loadavg")
	return strings.TrimSpace(string(load))
}

func getMemoryInfo() map[string]string {
	mem := make(map[string]string)
	data, _ := ioutil.ReadFile("/proc/meminfo")
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		parts := strings.Fields(line)
		if len(parts) < 2 {
			continue
		}
		key := strings.TrimSuffix(parts[0], ":")
		val := parts[1]
		if key == "MemTotal" {
			mem["total"] = fmt.Sprintf("%.0f MB", parseFloat(val)/1024)
		} else if key == "MemAvailable" {
			mem["available"] = fmt.Sprintf("%.0f MB", parseFloat(val)/1024)
		} else if key == "SwapTotal" {
			mem["swap_total"] = fmt.Sprintf("%.0f MB", parseFloat(val)/1024)
		} else if key == "SwapFree" {
			mem["swap_free"] = fmt.Sprintf("%.0f MB", parseFloat(val)/1024)
		}
	}
	return mem
}

func getStorageInfo() []map[string]string {
	var info []map[string]string
	cmd := exec.Command("df", "-h", "--output=target,size,used,avail,pcent")
	out, _ := cmd.Output()
	lines := strings.Split(strings.TrimSpace(string(out)), "\n")
	for i, line := range lines {
		if i == 0 || !strings.HasPrefix(line, "/") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) >= 5 {
			info = append(info, map[string]string{
				"mount":  fields[0],
				"size":   fields[1],
				"used":   fields[2],
				"avail":  fields[3],
				"use_pct": fields[4],
			})
		}
	}
	return info
}

func getNetworkInfo() map[string]string {
	info := make(map[string]string)
	cmd := exec.Command("hostname", "-I")
	out, _ := cmd.Output()
	info["ip"] = strings.TrimSpace(string(out))

	cmd = exec.Command("ip", "link", "show")
	out, _ = cmd.Output()
	lines := strings.Split(string(out), "\n")
	var ifaces []string
	for _, line := range lines {
		if strings.Contains(line, "@") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) > 0 && strings.HasSuffix(fields[0], ":") {
			iface := strings.TrimSuffix(fields[0], ":")
			if iface != "lo" {
				ifaces = append(ifaces, iface)
			}
		}
	}
	info["interfaces"] = strings.Join(ifaces, ", ")
	return info
}

func getServiceStatus() []map[string]string {
	targets := []string{"ssh", "smbd", "nmbd", "docker"}
	var status []map[string]string
	for _, svc := range targets {
		out, _ := runCmd("systemctl", "is-active", svc)
		status = append(status, map[string]string{
			"name":    svc,
			"status":  out,
			"enabled": "yes",
		})
	}
	return status
}

func getDiskDevices() []map[string]string {
	var devices []map[string]string
	cmd := exec.Command("lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT")
	out, _ := cmd.Output()
	var result map[string]interface{}
	json.Unmarshal(out, &result)
	if sv, ok := result["blockdevices"].([]interface{}); ok {
		for _, dev := range sv {
			if m, ok := dev.(map[string]interface{}); ok {
				devices = append(devices, map[string]string{
					"name":      fmt.Sprintf("%v", m["name"]),
					"size":      fmt.Sprintf("%v", m["size"]),
					"type":      fmt.Sprintf("%v", m["type"]),
					"mount":     fmt.Sprintf("%v", m["mountpoint"]),
				})
			}
		}
	}
	return devices
}

func parseFloat(s string) float64 {
	v, _ := strconv.ParseFloat(s, 64)
	return v
}

func writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}

func main() {
	fmt.Println("[NAS-WebUI] Starting on :8080")

	http.HandleFunc("/", handleIndex)
	http.HandleFunc("/status", handleStatus)
	http.HandleFunc("/restart", handleRestart)
	http.HandleFunc("/service", handleService)
	http.HandleFunc("/disk/mount", handleDiskMount)
	http.Handle("/static/", http.FileServer(http.Dir("/opt/nas/webui/")))

	addr := ":8080"
	go func() {
		if err := http.ListenAndServe(addr, nil); err != nil {
			fmt.Printf("[NAS-WebUI] Error: %v\n", err)
		}
	}()

	ticker := time.NewTicker(10 * time.Second)
	for range ticker.C {
		if isIdle() {
			fmt.Println("[NAS-WebUI] Idle timeout reached, shutting down.")
			shutdownOnce.Do(func() {
				os.Exit(0)
			})
		}
	}

	select {}
}