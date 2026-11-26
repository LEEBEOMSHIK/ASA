"use client";

import { Switch } from "./ui";
import "./access-management.css";

export type AccessMenu = { id: string; label: string; actions: string[] };
const actionOrder = ["view", "edit", "generate", "review", "approve", "delete"];
const generalMenus = new Set(["home", "agents", "tools", "characters", "automations", "video-comparison"]);
const labels: Record<string, string> = {
  view: "접근", edit: "수정", generate: "AI 생성·실행",
  review: "AI 검수", approve: "확정·해제", delete: "삭제",
};
const groups = [{ name: "일반 작업", general: true }, { name: "관리자", general: false }];

export function toggleAccessPermission(permissions: string[], menu: string, action: string) {
  const key = menu + "." + action;
  if (permissions.includes(key)) {
    return permissions.filter(permission => action === "view" ? !permission.startsWith(menu + ".") : permission !== key);
  }
  const added = [...permissions, key];
  return added.includes(menu + ".view") ? added : [...added, menu + ".view"];
}

export function AccessPermissionMatrix({ catalog, permissions, editable, onToggle }: {
  catalog: AccessMenu[];
  permissions: string[];
  editable: boolean;
  onToggle: (menu: string, action: string) => void;
}) {
  return <div className="access-matrix-groups">
    {groups.map(group => <section className="access-matrix-group" key={group.name} aria-label={group.name + " 메뉴 권한"}>
      <h3>{group.name}</h3>
      <table className="access-matrix">
        <caption className="sr-only">{group.name} 메뉴별 권한</caption>
        <thead><tr>
          <th scope="col">메뉴</th>
          {actionOrder.map(action => <th scope="col" key={action}>{labels[action]}</th>)}
        </tr></thead>
        <tbody>
          {catalog.filter(menu => generalMenus.has(menu.id) === group.general).map(menu => {
            const enabled = permissions.includes(menu.id + ".view");
            return <tr key={menu.id} className={enabled ? "" : "is-inaccessible"}>
              <th scope="row">
                <span>{menu.label}</span>
                <span className="access-mobile-state">{enabled ? "접근 허용" : "접근 차단"}</span>
              </th>
              {actionOrder.map(action => {
                const supported = menu.actions.includes(action);
                const cellClass = action === "view" ? "access-menu-toggle" : "access-operation";
                return <td key={action} className={cellClass + (supported ? "" : " is-unsupported")}>
                  {!supported ? <span aria-label="지원하지 않는 기능">—</span>
                    : action === "view" ? <Switch checked={enabled} disabled={!editable}
                      label={menu.label + " 접근 허용"} onChange={() => onToggle(menu.id, action)} />
                    : <label className="check-label">
                      <input type="checkbox" aria-label={menu.label + " · " + labels[action]}
                        checked={permissions.includes(menu.id + "." + action)}
                        disabled={!editable || !enabled} onChange={() => onToggle(menu.id, action)} />
                      <span className="access-cell-label">{labels[action]}</span>
                    </label>}
                </td>;
              })}
            </tr>;
          })}
        </tbody>
      </table>
    </section>)}
  </div>;
}
