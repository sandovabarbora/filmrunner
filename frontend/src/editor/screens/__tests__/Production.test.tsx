// @vitest-environment jsdom
/**
 * FR-147: the first real component-interaction test in this repo. Every test before this
 * one either exercised a pure function directly or used `renderToStaticMarkup`, which can
 * never fire a real user event — so nothing here has ever proven that an on-screen field
 * is actually wired to the state it claims to update. This test renders the crew-edit form
 * (`Crew`, from `../Production`) exactly as `ProductionScreen` mounts it, types into a real
 * input the way a user would, and asserts both what lands on screen and the data handed to
 * `crewEdits.ts`'s offline queue when the save fails — the path FR-144 found and fixed a real
 * bug in by only checking the pure diff function, never the form that drives it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api, ApiError, type Connection } from "../../api";
import { savePendingCrewEdit } from "../../crewEdits";
import type { CrewMember } from "../../../types";
import { Crew } from "../Production";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>("../../api");
  return {
    ...actual,
    api: {
      listCast: vi.fn().mockResolvedValue([]),
      listCrew: vi.fn(),
      searchContacts: vi.fn().mockResolvedValue([]),
      updateContact: vi.fn(),
      updateCrewMember: vi.fn(),
    },
  };
});

vi.mock("../../crewEdits", async () => {
  const actual = await vi.importActual<typeof import("../../crewEdits")>("../../crewEdits");
  return {
    ...actual,
    loadAllPendingCrewEdits: vi.fn().mockResolvedValue([]),
    savePendingCrewEdit: vi.fn().mockResolvedValue(undefined),
    clearPendingCrewEdit: vi.fn().mockResolvedValue(undefined),
  };
});

const conn: Connection = { apiBase: "https://api.example.test", token: "t" };

const member: CrewMember = {
  id: "member-1",
  production_id: "prod-1",
  contact_id: "contact-1",
  contact: { id: "contact-1", name: "Jana Nováková", phone: "+420 111 222 333", email: null, photo_url: null },
  department: "Camera",
  position: "1st AC",
  standard_call_time: "06:00",
  is_head_of_department: false,
  personal_token: "tok-1",
};

describe("Crew edit form", () => {
  beforeEach(() => {
    vi.mocked(api.listCrew).mockResolvedValue([member]);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("types a new phone number into a real field and queues it for sync when the save is offline", async () => {
    const setNotice = vi.fn();
    vi.mocked(api.updateContact).mockRejectedValue(new ApiError(0, "network error"));

    const user = userEvent.setup();
    render(<Crew conn={conn} productionId="prod-1" productionName="Test Production" canEdit setNotice={setNotice} />);

    const editButton = await screen.findByRole("button", { name: "Edit Jana Nováková" });
    await user.click(editButton);

    const phoneInput = await screen.findByLabelText("Phone");
    expect(phoneInput).toHaveValue("+420 111 222 333");
    await user.clear(phoneInput);
    await user.type(phoneInput, "+420 999 888 777");
    expect(phoneInput).toHaveValue("+420 999 888 777");

    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(setNotice).toHaveBeenCalledWith({
      kind: "warn",
      text: "No connection. The change is kept on this phone as not saved; it will sync when you are back online.",
    }));

    // The on-screen result: the form closed and the row now shows "not saved".
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    expect(screen.getByText("not saved")).toBeInTheDocument();

    // The data that reached crewEdits.ts's queuing path: only changed fields are queued.
    expect(savePendingCrewEdit).toHaveBeenCalledWith(expect.objectContaining({
      memberId: "member-1",
      contactId: "contact-1",
      patch: { phone: "+420 999 888 777" },
    }));
  });
});
